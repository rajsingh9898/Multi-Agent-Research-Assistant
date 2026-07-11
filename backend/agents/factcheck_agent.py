"""FactCheck Agent for Multi-Agent Research Assistant.

This agent extracts verifiable claims from summaries, queries Pinecone for evidence,
and calculates the overall report confidence score.
"""

from __future__ import annotations

import os
import json
import re
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from tools.pinecone_tool import query_claim_evidence
from tools.confidence import (
    calculate_confidence_score,
    get_confidence_label
)
from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager

load_dotenv()
logger = logging.getLogger(__name__)

# Constants
CLAIMS_PER_SUMMARY = 5
VERIFIED_THRESHOLD = 2
UNCERTAIN_THRESHOLD = 1
SUPPORT_SCORE_MIN = 0.5
MODEL = "gpt-4o-mini"

# Singleton client reference
_openai_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Retrieve the singleton OpenAI client, validating that the API key exists.

    Raises:
        ValueError: If OPENAI_API_KEY is not configured in the environment.
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY is missing from environment variables.")
            raise ValueError("OPENAI_API_KEY environment variable is not configured.")

        # Clean surrounding quotes from env if any
        cleaned_key = api_key.strip().strip('"').strip("'")
        _openai_client = OpenAI(api_key=cleaned_key)
        logger.info("OpenAI client successfully initialized in FactCheck Agent.")
        return _openai_client
    except Exception as exc:
        logger.exception("Failed to initialize OpenAI client in FactCheck Agent.")
        raise


def extract_claims(
    summary_text: str,
    question: str,
    num_claims: int = 5
) -> List[str]:
    """Uses GPT-4o-mini to extract top N factual claims from a summary text.

    Args:
        summary_text: The source text to analyze.
        question: The parent research question.
        num_claims: The max number of claims to extract.

    Returns:
        A list of clean claim strings.
    """
    if not summary_text or len(summary_text.strip()) < 15:
        logger.warning("Empty or very short summary text received for claim extraction.")
        return []

    try:
        client = get_openai_client()

        system_prompt = (
            "You are a fact extraction specialist. "
            "Extract specific, verifiable factual claims from research summaries. "
            "Return ONLY a JSON array of strings. No explanations. No markdown."
        )

        user_prompt = (
            f"Research Question: {question}\n\n"
            f"Summary Text:\n{summary_text}\n\n"
            f"Extract the {num_claims} most important specific factual claims from this summary.\n\n"
            "Requirements for each claim:\n"
            "1. Must be a single verifiable statement\n"
            "2. Must be specific (include numbers, dates, names when present)\n"
            "3. Must NOT be an opinion or prediction\n"
            "4. Must be self-contained (understandable alone)\n"
            "5. Avoid vague claims like \"studies show...\"\n\n"
            "Return ONLY a JSON array:\n"
            "[\"claim 1\", \"claim 2\", \"claim 3\", ...]"
        )

        response_text = ""
        for attempt in range(1, 4):
            try:
                logger.info(f"Calling ChatCompletions API for claim extraction (attempt {attempt}/3)...")
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=400,
                    temperature=0.1
                )
                response_text = response.choices[0].message.content or ""
                if response_text.strip():
                    break
            except Exception as exc:
                logger.warning(f"Claim extraction attempt {attempt} failed: {exc}")
                if attempt < 3:
                    time.sleep(2)
                else:
                    raise

        # Parsing response using 4 strategies
        claims: List[str] = []
        text_clean = response_text.strip()

        # Strategy 1: Direct JSON parse
        try:
            parsed = json.loads(text_clean)
            if isinstance(parsed, list):
                claims = [str(item) for item in parsed]
                logger.info("Direct JSON parse strategy succeeded in FactCheck.")
        except Exception:
            pass

        # Strategy 2: Extract JSON array using regex
        if not claims:
            try:
                match = re.search(r'\[.*\]', text_clean, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        claims = [str(item) for item in parsed]
                        logger.info("Regex JSON extraction strategy succeeded in FactCheck.")
            except Exception:
                pass

        # Strategy 3: Split by newlines and clean list formats
        if not claims:
            try:
                lines = text_clean.split("\n")
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    # Strip list indicators like "1. ", "- ", etc.
                    cleaned = re.sub(r'^(?:\d+\.\s*|[-*+]\s*)', '', line_stripped).strip()
                    cleaned = cleaned.strip('"').strip("'").strip()
                    if len(cleaned) >= 15:
                        claims.append(cleaned)
                if claims:
                    logger.info("Newline split parsing strategy succeeded in FactCheck.")
            except Exception:
                pass

        # Cleaning, filtering and slicing claims
        cleaned_claims = []
        for claim in claims:
            c_clean = claim.strip()
            if len(c_clean) >= 15:
                cleaned_claims.append(c_clean)

        final_claims = cleaned_claims[:num_claims]
        logger.info(f"Extracted {len(final_claims)} claims from summary.")
        return final_claims

    except Exception as exc:
        logger.error(f"Error extracting claims from summary (preview: '{summary_text[:60]}...'): {exc}", exc_info=True)
        return []


async def verify_single_claim(
    claim: str,
    report_id: str,
    question: str
) -> Dict[str, Any]:
    """Verifies ONE claim against the Pinecone index.

    Args:
        claim: The factual claim string to verify.
        report_id: The unique active report ID.
        question: The sub-question the claim belongs to.

    Returns:
        A dict detailing verification outcomes.
    """
    if not claim or not claim.strip():
        return {
            "claim": "",
            "status": "unverified",
            "supporting_sources": [],
            "evidence_count": 0,
            "avg_support_score": 0.0,
            "source_question": question,
            "credibility_levels": []
        }

    try:
        evidence_chunks = await query_claim_evidence(
            claim=claim,
            report_id=report_id,
            top_k=5
        )

        if not evidence_chunks:
            return {
                "claim": claim,
                "status": "unverified",
                "supporting_sources": [],
                "evidence_count": 0,
                "avg_support_score": 0.0,
                "source_question": question,
                "credibility_levels": []
            }

        # Filter chunks that pass the minimum support score
        strong_support = [
            c for c in evidence_chunks
            if c.get("score", 0.0) >= SUPPORT_SCORE_MIN
        ]

        # Extract unique supporting source URLs
        seen_urls = set()
        unique_sources = []
        for chunk in strong_support:
            url = chunk.get("source_url", "")
            if url and url not in seen_urls:
                unique_sources.append(url)
                seen_urls.add(url)

        # Extract credibility levels safely (handles strings and dict structures)
        credibility_levels_set = set()
        for c in strong_support:
            cred_val = c.get("credibility", "unknown")
            if isinstance(cred_val, dict):
                credibility_levels_set.add(cred_val.get("rating") or cred_val.get("label") or "unknown")
            else:
                credibility_levels_set.add(cred_val or "unknown")
        credibility_levels = list(credibility_levels_set)

        # Calculate average support score
        if strong_support:
            avg_score = sum(c.get("score", 0.0) for c in strong_support) / len(strong_support)
        else:
            avg_score = 0.0

        evidence_count = len(unique_sources)

        # Assign status based on evidence count
        if evidence_count >= VERIFIED_THRESHOLD:
            status = "verified"
        elif evidence_count >= UNCERTAIN_THRESHOLD:
            status = "uncertain"
        else:
            status = "unverified"

        return {
            "claim": claim,
            "status": status,
            "supporting_sources": unique_sources,
            "evidence_count": evidence_count,
            "avg_support_score": round(avg_score, 3),
            "source_question": question,
            "credibility_levels": credibility_levels
        }

    except Exception as exc:
        logger.error(f"Error verifying claim '{claim[:40]}...': {exc}", exc_info=True)
        return {
            "claim": claim,
            "status": "unverified",
            "supporting_sources": [],
            "evidence_count": 0,
            "avg_support_score": 0.0,
            "source_question": question,
            "credibility_levels": []
        }


async def process_single_summary(
    summary_dict: Dict[str, Any],
    summary_index: int,
    total_summaries: int,
    report_id: str,
    state: AgentMemory
) -> List[Dict[str, Any]]:
    """Extracts and verifies claims from a single summary.

    Args:
        summary_dict: Dict representing a single sub-question summary.
        summary_index: 1-based index of the current summary.
        total_summaries: Total summary count.
        report_id: Unique string identifying the report.
        state: Memory state context.

    Returns:
        List of claim verification results.
    """
    question = summary_dict.get("question", "")
    summary_text = summary_dict.get("summary", "")

    # Emit progress
    await ws_manager.emit_agent_update(
        report_id, "factcheck_agent",
        f"Extracting claims from summary {summary_index}/{total_summaries}..."
    )

    # Extract claims
    claims = extract_claims(
        summary_text=summary_text,
        question=question,
        num_claims=CLAIMS_PER_SUMMARY
    )

    if not claims:
        logger.warning(f"No claims extracted from summary {summary_index}")
        await ws_manager.emit_thinking(report_id, "factcheck_agent", "No claims extracted")
        return []

    # Emit thinking log
    await ws_manager.emit_thinking(
        report_id, "factcheck_agent",
        f"Summary {summary_index}: extracted {len(claims)} claims to verify"
    )

    # ── PARALLEL VERIFICATION ──
    # Limit concurrent Pinecone queries to 5
    semaphore = asyncio.Semaphore(5)

    async def verify_with_semaphore(claim_val, claim_i):
        async with semaphore:
            await ws_manager.emit_agent_update(
                report_id, "factcheck_agent",
                f"Verifying claim {claim_i}/{len(claims)}: {claim_val[:45]}..."
            )
            res = await verify_single_claim(
                claim=claim_val,
                report_id=report_id,
                question=question
            )
            # Emit thinking with emoji indicators
            status_emoji = {
                "verified": "✅",
                "uncertain": "⚠️",
                "unverified": "❌"
            }.get(res["status"], "❓")

            await ws_manager.emit_thinking(
                report_id, "factcheck_agent",
                f"{status_emoji} '{claim_val[:45]}...' -> {res['status']} ({res['evidence_count']} sources)"
            )

            state.add_thinking_log(
                "factcheck_agent",
                f"Claim {claim_i}: {res['status']} - {res['evidence_count']} supporting sources"
            )
            return res

    verify_tasks = [
        verify_with_semaphore(claim, idx)
        for idx, claim in enumerate(claims, 1)
    ]

    raw_results = await asyncio.gather(*verify_tasks, return_exceptions=True)
    results = []

    for result in raw_results:
        if isinstance(result, Exception):
            logger.error(f"Claim verification error: {result}")
        elif result is not None:
            results.append(result)

    logger.info(f"Summary {summary_index}: {len(results)} claims verified.")

    return results


def calculate_verification_stats(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate statistics across all claim verifications.

    Args:
        all_results: List of verification dicts.

    Returns:
        Structured statistics summary.
    """
    total = len(all_results)
    verified = sum(1 for r in all_results if r.get("status") == "verified")
    uncertain = sum(1 for r in all_results if r.get("status") == "uncertain")
    unverified = sum(1 for r in all_results if r.get("status") == "unverified")

    verification_rate = (verified + uncertain) / total if total > 0 else 0.0

    return {
        "total_claims": total,
        "verified": verified,
        "uncertain": uncertain,
        "unverified": unverified,
        "verification_rate": round(verification_rate, 2),
        "passed_claims": verified + uncertain,
        "failed_claims": unverified
    }


async def run(
    state: AgentMemory,
    report_id: str
) -> bool:
    """Entry point for the FactCheck Agent called by orchestrator run_pipeline().

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        True if check finished successfully, else False.
    """
    try:
        state.set_current_agent("factcheck_agent")

        summaries = state.get_all_summaries()
        if not summaries:
            error = "No summaries to fact-check"
            state.set_error(error)
            await ws_manager.emit_error(report_id, "factcheck_agent", error)
            return False

        total = len(summaries)

        await ws_manager.emit_agent_start(
            report_id, "factcheck_agent",
            f"Verifying claims from {total} summaries..."
        )

        state.add_log(
            "factcheck_agent", "start",
            f"Starting fact-check on {total} summaries"
        )

        # ── PARALLEL SUMMARY PROCESSING ──
        # Limit concurrent summary processing to 2 because each verification is already parallel
        semaphore = asyncio.Semaphore(2)

        async def process_with_semaphore(summary, index):
            async with semaphore:
                return await process_single_summary(
                    summary_dict=summary,
                    summary_index=index,
                    total_summaries=total,
                    report_id=report_id,
                    state=state
                )

        summary_tasks = [
            process_with_semaphore(s, i+1)
            for i, s in enumerate(summaries)
        ]

        raw_results = await asyncio.gather(*summary_tasks, return_exceptions=True)

        all_results = []
        for result in raw_results:
            if isinstance(result, Exception):
                logger.error(f"Summary process error: {result}")
            elif isinstance(result, list):
                all_results.extend(result)


        if not all_results:
            error = "No claims could be extracted"
            state.set_error(error)
            await ws_manager.emit_error(report_id, "factcheck_agent", error)
            return False

        # Store results in memory
        state.update_state("verified_claims", all_results)

        # Calculate stats and confidence score
        stats = calculate_verification_stats(all_results)
        confidence = calculate_confidence_score(state.get_state())
        state.update_state("confidence_score", confidence)
        label_info = get_confidence_label(confidence)

        # Log completion
        state.add_log(
            "factcheck_agent", "done",
            f"Verified {stats['verified']}/{stats['total_claims']} claims. Confidence: {confidence}%"
        )

        state.add_thinking_log(
            "factcheck_agent",
            f"Fact-check complete. Verified: {stats['verified']}, Uncertain: {stats['uncertain']}, "
            f"Unverified: {stats['unverified']}. Confidence: {confidence}% ({label_info['label']})"
        )

        # Emit completion
        await ws_manager.emit_agent_done(
            report_id, "factcheck_agent",
            f"Verified {stats['passed_claims']}/{stats['total_claims']} claims. Confidence score: {confidence}%",
            data={
                "total_claims": stats["total_claims"],
                "verified": stats["verified"],
                "uncertain": stats["uncertain"],
                "unverified": stats["unverified"],
                "confidence_score": confidence,
                "confidence_label": label_info["label"],
                "confidence_emoji": label_info["emoji"]
            }
        )

        # Hand off to Writer Agent
        state.set_current_agent("writer_agent")
        return True

    except Exception as exc:
        error_msg = f"FactCheck Agent failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "factcheck_agent", error_msg)
        return False


def get_verified_only(state: AgentMemory) -> List[Dict[str, Any]]:
    """Helper for Writer Agent returning only verified and uncertain claims.

    Args:
        state: Agent memory context.

    Returns:
        List of claims matching verified or uncertain statuses.
    """
    all_claims = state.get_field("verified_claims", []) or []
    return [
        c for c in all_claims
        if isinstance(c, dict) and c.get("status") in ["verified", "uncertain"]
    ]


def get_factcheck_summary(state: AgentMemory) -> Dict[str, Any]:
    """Helper returning debugging and verification summary statistics.

    Args:
        state: Agent memory context.

    Returns:
        A statistics and status dictionary.
    """
    all_claims = state.get_field("verified_claims", []) or []
    if not all_claims:
        return {}

    stats = calculate_verification_stats(all_claims)
    confidence = state.get_field("confidence_score", 0)
    label = get_confidence_label(confidence)

    return {
        **stats,
        "confidence_score": confidence,
        "confidence_label": label.get("label", "unknown"),
        "confidence_emoji": label.get("emoji", "❓"),
        "top_verified_claims": [
            c.get("claim", "") for c in all_claims
            if isinstance(c, dict) and c.get("status") == "verified"
        ][:3],
        "removed_claims": [
            c.get("claim", "") for c in all_claims
            if isinstance(c, dict) and c.get("status") == "unverified"
        ]
    }
