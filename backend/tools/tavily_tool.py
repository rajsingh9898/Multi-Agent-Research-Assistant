"""Tavily search tool implementation for Multi-Agent Research Assistant.

This tool coordinates calls to the Tavily Search API, performs quality filtering,
enriches the metadata with credibility rankings, and produces statistical summaries.
"""

from __future__ import annotations

import os
import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests

from tavily import TavilyClient
from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError

logger = logging.getLogger(__name__)

# Global singleton client instance
_TAVILY_CLIENT_INSTANCE: Optional[TavilyClient] = None


def initialize_tavily() -> TavilyClient:
    """Initialize and return the TavilyClient singleton.

    Reads TAVILY_API_KEY from environment, raises ValueError if missing.
    """
    global _TAVILY_CLIENT_INSTANCE
    if _TAVILY_CLIENT_INSTANCE is not None:
        return _TAVILY_CLIENT_INSTANCE

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY environment variable is missing")
        raise ValueError("TAVILY_API_KEY is not configured in .env file.")

    # Strip any potential surrounding quotes from the dotenv load
    api_key = api_key.strip("'\"")

    try:
        _TAVILY_CLIENT_INSTANCE = TavilyClient(api_key=api_key)
        logger.info("TavilyClient singleton successfully initialized")
        return _TAVILY_CLIENT_INSTANCE
    except Exception as e:
        logger.exception("Failed to initialize TavilyClient")
        raise RuntimeError(f"Failed to initialize TavilyClient: {e}") from e


def _normalize_hostname(url: str) -> str:
    """Extract a lowercase hostname from any URL-like value."""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        hostname = (parsed.hostname or "").lower().strip()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""


def emit_thinking_log(report_id: str, thought: str) -> None:
    """Log a thought, broadcast it to WebSockets, and append to in-memory/Firestore stores."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "agent": "search",
        "thought": thought,
        "timestamp": timestamp
    }

    # 1. Log to Python standard logger
    logger.info(f"[{report_id}] {thought}")

    # 2. Append to REPORT_STORE dynamically to avoid circular import issues
    try:
        from main import REPORT_STORE
        if report_id and report_id in REPORT_STORE:
            if "thinking_logs" not in REPORT_STORE[report_id]:
                REPORT_STORE[report_id]["thinking_logs"] = []
            REPORT_STORE[report_id]["thinking_logs"].append(log_entry)
            logger.debug(f"Appended thinking log to REPORT_STORE for {report_id}")
    except Exception as e:
        logger.debug(f"Failed to append thinking log to REPORT_STORE: {e}")

    # 3. Save to Firestore if available
    try:
        from utils.firebase_config import get_firestore
        from firebase_admin import firestore
        db = get_firestore()
        if report_id:
            report_ref = db.collection("reports").document(report_id)
            # Safe update check using transaction or direct update if exists
            doc = report_ref.get()
            if doc.exists:
                report_ref.update({
                    "thinking_logs": firestore.ArrayUnion([log_entry])
                })
                logger.debug(f"Appended thinking log to Firestore for {report_id}")
    except Exception as e:
        logger.debug(f"Failed to append thinking log to Firestore: {e}")

    # 4. Broadcast via WebSocket
    try:
        from utils.websocket_manager import broadcast
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    broadcast(report_id, {
                        "event": "thinking",
                        "agent": "search",
                        "thought": thought,
                        "report_id": report_id,
                        "timestamp": timestamp
                    }),
                    loop
                )
        except RuntimeError:
            # No running loop, start a temporary one
            asyncio.run(broadcast(report_id, {
                "event": "thinking",
                "agent": "search",
                "thought": thought,
                "report_id": report_id,
                "timestamp": timestamp
            }))
    except Exception as e:
        logger.debug(f"Failed to broadcast thinking log: {e}")


def search(query: str, max_results: int = 4, search_depth: str = "basic") -> List[Dict[str, Any]]:
    """Call Tavily API and return raw search results list.

    Validates query, handles rate limit (429) retries, timeout retries,
    and returns empty list if no results are found.
    """
    if not query or not query.strip():
        logger.warning("Empty search query provided")
        return []

    # Truncate to 400 characters if too long
    if len(query) > 400:
        logger.info(f"Query length is {len(query)} chars. Truncating to 400 chars.")
        query = query[:400]

    client = initialize_tavily()

    timeout_retries = 3
    timeout_delay = 2.0
    rate_limit_retried = False

    attempt = 0
    while attempt <= timeout_retries:
        try:
            logger.info(f"Executing Tavily search. Query: {query} | Max results: {max_results} | Depth: {search_depth}")
            response = client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results
            )
            results = response.get("results", [])
            if not results:
                logger.info("Tavily search returned no results.")
                return []
            return results

        except InvalidAPIKeyError as exc:
            logger.error("Tavily API Key is invalid (401).")
            raise ValueError(f"Invalid Tavily API key: {exc}") from exc

        except UsageLimitExceededError as exc:
            if not rate_limit_retried:
                logger.warning("Tavily Rate Limit or Usage Limit exceeded (429). Retrying after 60s delay...")
                time.sleep(60.0)
                rate_limit_retried = True
                continue
            else:
                logger.error("Tavily API limit exceeded again after 60s cooldown.")
                raise RuntimeError(f"Tavily usage limit exceeded: {exc}") from exc

        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as exc:
            attempt += 1
            if attempt <= timeout_retries:
                logger.warning(f"Tavily timeout encountered (attempt {attempt}/{timeout_retries}). Retrying in {timeout_delay}s... Error: {exc}")
                time.sleep(timeout_delay)
            else:
                logger.error("Tavily search timed out. Max retries exhausted.")
                return []

        except Exception as exc:
            # Handle potential HTTP Errors raised by requests underlying client
            if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
                status_code = exc.response.status_code
                if status_code == 401:
                    logger.error("Tavily 401 Unauthorized HTTP response.")
                    raise ValueError(f"Invalid Tavily API key: {exc}") from exc
                elif status_code == 429:
                    if not rate_limit_retried:
                        logger.warning("Tavily 429 Rate Limit HTTP response. Retrying after 60s delay...")
                        time.sleep(60.0)
                        rate_limit_retried = True
                        continue
                    else:
                        logger.error("Tavily 429 Limit exceeded after 60s cooldown.")
                        raise RuntimeError(f"Tavily API limit exceeded: {exc}") from exc

            logger.exception("Unexpected exception during Tavily search")
            return []

    return []


def filter_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove low score, short content, blocked domains, and duplicate URLs.

    Logs statistics of how many items were filtered out.
    """
    if not results:
        return []

    blocked_domains = {
        "pinterest.com", "reddit.com", "quora.com", "twitter.com",
        "facebook.com", "instagram.com", "tiktok.com", "youtube.com",
        "amazon.com", "ebay.com", "wikihow.com", "answers.com"
    }

    filtered: List[Dict[str, Any]] = []
    seen_urls = set()

    score_filtered = 0
    content_len_filtered = 0
    domain_filtered = 0
    duplicate_filtered = 0

    for item in results:
        url = item.get("url", "").strip()
        content = item.get("content", "").strip()
        score = item.get("score", 0.0)

        # 1. Duplicate URLs
        if url in seen_urls:
            duplicate_filtered += 1
            continue

        # 2. Score check
        if score < 0.3:
            score_filtered += 1
            continue

        # 3. Content length check
        if len(content) < 100:
            content_len_filtered += 1
            continue

        # 4. Blocked domain check
        hostname = _normalize_hostname(url)
        is_blocked = False
        for blocked in blocked_domains:
            if hostname == blocked or hostname.endswith(f".{blocked}"):
                is_blocked = True
                break

        if is_blocked:
            domain_filtered += 1
            continue

        seen_urls.add(url)
        filtered.append(item)

    total_filtered = score_filtered + content_len_filtered + domain_filtered + duplicate_filtered
    logger.info(
        f"Filtered results: {len(filtered)} retained, {total_filtered} discarded. "
        f"(Low score: {score_filtered}, Short content: {content_len_filtered}, "
        f"Blocked domain: {domain_filtered}, Duplicate URL: {duplicate_filtered})"
    )

    return filtered


def format_results(results: List[Dict[str, Any]], sub_question: str) -> List[Dict[str, Any]]:
    """Convert each result to the AgentState format.

    Enriches with credibility ratings, word counts, and sub-question mapping.
    """
    from tools.credibility import rate_source_credibility

    formatted: List[Dict[str, Any]] = []
    for item in results:
        url = item.get("url", "").strip()
        content = item.get("content", "").strip()
        title = item.get("title", "Untitled Source").strip()
        score = item.get("score", 0.0)
        published_date = item.get("published_date")

        # Get credibility metadata
        credibility_info = rate_source_credibility(url)

        # Word count estimate
        word_count = len(content.split()) if content else 0

        formatted_source = {
            "title": title,
            "url": url,
            "content": content,
            "tavily_score": float(score),
            "credibility": credibility_info.get("rating", "Unknown"),
            "credibility_score": int(credibility_info.get("score", 40)),
            "credibility_label": credibility_info.get("label", "Unknown"),
            "credibility_icon": credibility_info.get("emoji", "❔"),
            "word_count": word_count,
            "sub_question": sub_question,
            "formatted_date": published_date
        }
        formatted.append(formatted_source)

    return formatted


def search_for_question(question: str, report_id: str) -> Dict[str, Any]:
    """Complete pipeline execution for a single sub-question.

    Performs query search, filters results, formats results, emits logs, and calculates average credibility.
    """
    # Emit thinking log
    emit_thinking_log(report_id, f"Searching web for: {question}")

    # Search
    raw_results = search(query=question, max_results=4, search_depth="basic")

    # Filter
    filtered_results = filter_results(raw_results)

    # Format
    formatted_list = format_results(filtered_results, question)

    # Calculate average credibility score
    from tools.credibility import calculate_average_credibility
    avg_score = int(round(calculate_average_credibility(formatted_list)))

    return {
        "question": question,
        "sources": formatted_list,
        "source_count": len(formatted_list),
        "avg_credibility_score": avg_score
    }


def search_all_questions(sub_questions: List[str], report_id: str) -> List[Dict[str, Any]]:
    """Loop through all sub-questions sequentially, sleeping 1s between calls to avoid rate limits."""
    results: List[Dict[str, Any]] = []
    total = len(sub_questions)

    for idx, question in enumerate(sub_questions, 1):
        progress_str = f"Searching {idx}/{total}: {question}"
        logger.info(progress_str)
        emit_thinking_log(report_id, progress_str)

        res = search_for_question(question, report_id)
        results.append(res)

        if idx < total:
            time.sleep(1.0)

    return results


def get_search_summary(search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate aggregate statistics and top sources from complete search results list."""
    total_questions = len(search_results)
    all_sources: List[Dict[str, Any]] = []

    for q_res in search_results:
        all_sources.extend(q_res.get("sources", []))

    total_sources = len(all_sources)

    # Calculate average credibility across all collected sources
    from tools.credibility import calculate_average_credibility
    avg_credibility = int(round(calculate_average_credibility(all_sources)))

    # Breakdown by category
    breakdown = {
        "academic": 0,
        "news": 0,
        "blog": 0,
        "unknown": 0
    }

    for src in all_sources:
        cred = (src.get("credibility") or "Unknown").lower()
        if "academic" in cred or "government" in cred:
            breakdown["academic"] += 1
        elif "news" in cred:
            breakdown["news"] += 1
        elif "blog" in cred:
            breakdown["blog"] += 1
        else:
            breakdown["unknown"] += 1

    # Extract top 3 unique sources by credibility score, resolved by tavily score
    unique_sources_map: Dict[str, Dict[str, Any]] = {}
    for src in all_sources:
        url = src.get("url")
        if url:
            existing = unique_sources_map.get(url)
            if not existing or src.get("credibility_score", 0) > existing.get("credibility_score", 0):
                unique_sources_map[url] = src

    unique_sources = list(unique_sources_map.values())
    unique_sources.sort(key=lambda x: (x.get("credibility_score", 0), x.get("tavily_score", 0.0)), reverse=True)
    top_sources = unique_sources[:3]

    return {
        "total_questions": total_questions,
        "total_sources": total_sources,
        "avg_credibility": avg_credibility,
        "credibility_breakdown": breakdown,
        "top_sources": top_sources
    }
