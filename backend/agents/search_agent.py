"""Search Agent for the Multi-Agent Research Assistant.

This agent handles web searches for each sub-question, tracks credibility ratings,
and manages state updates and live notifications.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

from tools.tavily_tool import (
    search_for_question,
    search_all_questions,
    get_search_summary
)
from tools.credibility import (
    calculate_average_credibility
)
from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


def validate_sub_questions(state: AgentMemory) -> List[str]:
    """Validate and clean the sub-questions list stored in state.

    Args:
        state: Agent memory context.

    Returns:
        List of valid cleaned question strings.
    """
    try:
        sub_questions = state.get_field("sub_questions")
        if not sub_questions:
            logger.error("No sub-questions in state")
            return []

        cleaned = []
        for q in sub_questions:
            if not isinstance(q, str):
                continue
            q_stripped = q.strip()
            if not q_stripped:
                continue
            if len(q_stripped) < 10:
                continue
            cleaned.append(q_stripped)

        logger.info(f"Validated {len(cleaned)} sub-questions")
        return cleaned
    except Exception as exc:
        logger.exception("Error validating sub-questions")
        return []


async def search_single_question(
    question: str,
    question_index: int,
    total_questions: int,
    report_id: str,
    state: AgentMemory
) -> Optional[Dict[str, Any]]:
    """Execute search for a single sub-question.

    Args:
        question: The search query question string.
        question_index: The 1-based index of this question.
        total_questions: The total count of questions.
        report_id: The active report identifier.
        state: The agent memory context.

    Returns:
        The search results dictionary or None if it failed.
    """
    try:
        # 1. Emit agent_update
        msg = f"Searching Q{question_index}/{total_questions}: {question[:60]}..."
        await ws_manager.emit_agent_update(
            report_id,
            "search_agent",
            msg,
            data={
                "current": question_index,
                "total": total_questions,
                "question": question
            }
        )

        # 2. Add thinking_log
        state.add_thinking_log("search_agent", f"Searching for: {question}")

        # 3. Call search_for_question() from tavily_tool
        result = search_for_question(question=question, report_id=report_id)

        # 4. Handle empty results
        source_count = result.get("source_count", 0)
        if source_count == 0:
            logger.warning(f"No sources found for: {question}")
            await ws_manager.emit_thinking(
                report_id,
                "search_agent",
                f"No sources found for Q{question_index}, will skip in summary"
            )
            return result

        # 5. After successful search
        avg_score = result.get("avg_credibility_score", 0)
        await ws_manager.emit_thinking(
            report_id,
            "search_agent",
            f"Q{question_index} found {source_count} sources, avg credibility: {avg_score}"
        )

        sources = result.get("sources", [])
        if sources:
            best = max(sources, key=lambda s: s.get("tavily_score", 0.0))
            logger.info(f"Best source: {best.get('url')} ({best.get('credibility')})")

        # 6. Small delay between searches
        await asyncio.sleep(0.5)

        return result

    except Exception as exc:
        logger.error(f"Error searching single question '{question}': {exc}", exc_info=True)
        await ws_manager.emit_thinking(
            report_id,
            "search_agent",
            f"Failed search for Q{question_index}: {exc}"
        )
        return None


def collect_all_source_credibility(search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect credibility details from all search result sources.

    Args:
        search_results: The aggregated search results.

    Returns:
        A list of unified credibility payloads.
    """
    try:
        credibility_data = []
        for result in search_results:
            if not isinstance(result, dict):
                continue
            sub_q = result.get("question", "")
            for src in result.get("sources", []):
                if not isinstance(src, dict):
                    continue
                credibility_data.append({
                    "url": src.get("url"),
                    "title": src.get("title"),
                    "rating": src.get("credibility"),
                    "score": src.get("credibility_score"),
                    "sub_question": sub_q
                })
        return credibility_data
    except Exception as exc:
        logger.exception("Error collecting source credibility data")
        return []


async def run(state: AgentMemory, report_id: str) -> bool:
    """Run coordinates web search agent pipeline.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        Boolean indicating search pipeline success.
    """
    try:
        # -- SETUP --
        state.set_current_agent("search_agent")

        # Validate sub-questions exist
        sub_questions = validate_sub_questions(state)

        if not sub_questions:
            state.set_error("No sub-questions to search for")
            await ws_manager.emit_error(
                report_id, "search_agent",
                "No research questions available"
            )
            return False

        total = len(sub_questions)

        # -- START --
        await ws_manager.emit_agent_start(
            report_id, "search_agent",
            f"Searching web for {total} questions..."
        )

        state.add_log(
            "search_agent", "start",
            f"Beginning search for {total} questions"
        )

        # -- SEARCH EACH QUESTION --
        search_results = []
        failed_questions = []

        for i, question in enumerate(sub_questions, 1):
            result = await search_single_question(
                question=question,
                question_index=i,
                total_questions=total,
                report_id=report_id,
                state=state
            )

            if result is not None:
                search_results.append(result)
            else:
                failed_questions.append(question)
                logger.warning(f"Question {i} search failed")

        # -- HANDLE COMPLETE FAILURE --
        if not search_results:
            state.set_error("All searches failed")
            await ws_manager.emit_error(
                report_id, "search_agent",
                "Could not find any sources"
            )
            return False

        # -- STORE RESULTS --
        state.update_state("search_results", search_results)

        # -- COLLECT CREDIBILITY DATA --
        credibility_data = collect_all_source_credibility(search_results)
        state.update_state("source_credibility", credibility_data)

        # -- CALCULATE SUMMARY --
        summary = get_search_summary(search_results)

        total_sources = summary.get("total_sources", 0)
        avg_credibility = summary.get("avg_credibility", 0)
        breakdown = summary.get("credibility_breakdown", {})

        # -- LOG COMPLETION --
        state.add_log(
            "search_agent", "done",
            f"Found {total_sources} sources from {len(search_results)} questions"
        )

        state.add_thinking_log(
            "search_agent",
            f"Search complete. Academic: {breakdown.get('academic', 0)}, "
            f"News: {breakdown.get('news', 0)}, Blog: {breakdown.get('blog', 0)}"
        )

        # Log failed questions if any
        if failed_questions:
            state.add_log(
                "search_agent", "warning",
                f"{len(failed_questions)} questions returned no results"
            )

        # -- EMIT COMPLETION --
        await ws_manager.emit_agent_done(
            report_id, "search_agent",
            f"Search complete: {total_sources} sources from {len(search_results)} questions",
            data={
                "total_sources": total_sources,
                "total_questions": len(search_results),
                "avg_credibility": avg_credibility,
                "credibility_breakdown": breakdown,
                "failed_questions": len(failed_questions)
            }
        )

        # -- HAND OFF TO NEXT AGENT --
        state.set_current_agent("summary_agent")

        return True

    except Exception as exc:
        error_msg = f"Search agent failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "search_agent", error_msg)
        return False


def get_search_stats(state: AgentMemory) -> Dict[str, Any]:
    """Retrieve detailed search execution statistics for debugging and test reporting.

    Args:
        state: The memory state instance.

    Returns:
        A dictionary containing structured metrics and breakdowns.
    """
    try:
        search_results = state.get_field("search_results")
        if not search_results:
            return {}

        total_questions_searched = len(search_results)
        all_sources = []
        questions_with_no_sources = 0
        sources_per_question = []

        for r in search_results:
            if not isinstance(r, dict):
                continue
            q = r.get("question", "")
            src_list = r.get("sources", [])
            src_count = len(src_list)
            
            all_sources.extend(src_list)
            if src_count == 0:
                questions_with_no_sources += 1
            
            sources_per_question.append({
                "question": q[:50],
                "count": src_count
            })

        total_sources_found = len(all_sources)
        avg_sources_per_question = (
            total_sources_found / total_questions_searched
            if total_questions_searched > 0 else 0.0
        )

        avg_credibility_score = int(round(calculate_average_credibility(all_sources)))

        credibility_breakdown = {
            "academic": 0,
            "news": 0,
            "blog": 0,
            "unknown": 0
        }
        for src in all_sources:
            cred = str(src.get("credibility") or "unknown").lower().strip()
            if cred in credibility_breakdown:
                credibility_breakdown[cred] += 1
            else:
                credibility_breakdown["unknown"] += 1

        top_sources = []
        for src in all_sources:
            top_sources.append({
                "url": src.get("url"),
                "title": src.get("title"),
                "credibility": src.get("credibility"),
                "score": src.get("credibility_score"),
                "tavily_score": src.get("tavily_score", 0.0)
            })
        top_sources.sort(key=lambda s: s.get("tavily_score", 0.0), reverse=True)

        top_3_sources = []
        for item in top_sources[:3]:
            top_3_sources.append({
                "url": item["url"],
                "title": item["title"],
                "credibility": item["credibility"],
                "score": item["score"]
            })

        return {
            "total_questions_searched": total_questions_searched,
            "total_sources_found": total_sources_found,
            "questions_with_no_sources": questions_with_no_sources,
            "avg_sources_per_question": avg_sources_per_question,
            "avg_credibility_score": avg_credibility_score,
            "credibility_breakdown": credibility_breakdown,
            "top_3_sources": top_3_sources,
            "sources_per_question": sources_per_question
        }

    except Exception as exc:
        logger.exception("Error generating search statistics")
        return {}
