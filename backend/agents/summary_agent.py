"""Summary Agent for the Multi-Agent Research Assistant.

This agent handles flattening raw search results, dividing source content
into overlapping text segments (chunks), generating embedding vectors, and
storing them in the Pinecone vector database.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

from tools.pinecone_tool import (
    upsert_source_chunks,
    chunk_text,
    get_index_stats,
    delete_report_chunks
)
from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Alias to satisfy the Day 10 naming specification
chunk_content = chunk_text



def validate_search_results(state: AgentMemory) -> List[Dict[str, Any]]:
    """Validate that search results exist in memory before running storage.

    Args:
        state: Agent memory context.

    Returns:
        List of valid search result structures containing sources.
    """
    try:
        search_results = state.get_field("search_results")
        if not search_results:
            logger.error("No search results found in state.")
            return []

        cleaned = []
        for r in search_results:
            if not isinstance(r, dict):
                continue
            sources = r.get("sources", [])
            if isinstance(sources, list) and len(sources) > 0:
                cleaned.append(r)

        logger.info(f"Validated {len(cleaned)} questions with sources to process")
        return cleaned
    except Exception as exc:
        logger.exception("Error validating search results.")
        return []


def get_all_sources_flat(search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten search results into a flat list of sources with index keys.

    Args:
        search_results: The validated nested search result list.

    Returns:
        A list of flattened source dictionary structures.
    """
    try:
        flat_sources = []
        global_index = 0
        for r in search_results:
            sub_q = r.get("question", "")
            for src in r.get("sources", []):
                if not isinstance(src, dict):
                    continue
                src_copy = dict(src)
                src_copy["global_index"] = global_index
                src_copy["source_index"] = global_index
                src_copy["sub_question"] = sub_q
                flat_sources.append(src_copy)
                global_index += 1
        return flat_sources
    except Exception as exc:
        logger.exception("Error flattening search result sources.")
        return []


async def process_single_source(
    source: Dict[str, Any],
    source_index: int,
    total_sources: int,
    report_id: str,
    state: AgentMemory
) -> Dict[str, Any]:
    """Process a single source by chunking, embedding, and upserting to Pinecone.

    Args:
        source: Flat source dictionary.
        source_index: 1-based index representing current progress.
        total_sources: Total count of sources to process.
        report_id: Unique string identifying the active report.
        state: Agent memory context.

    Returns:
        A dictionary summarizing the result of this source's processing.
    """
    try:
        content = source.get("content", "")
        url = source.get("url", "")
        title = source.get("title", "Unknown")
        credibility = source.get("credibility", "unknown")
        sub_question = source.get("sub_question", "")

        # 2. Validate content
        if not content or len(content.strip()) < 50:
            logger.warning(f"Skipping {url}: no content or text too short.")
            return {
                "url": url,
                "chunks": 0,
                "status": "skipped",
                "reason": "empty content"
            }

        # 3. Emit agent_update
        msg = f"Processing source {source_index}/{total_sources}: {title[:40]}..."
        await ws_manager.emit_agent_update(
            report_id,
            "summary_agent",
            msg,
            data={
                "current": source_index,
                "total": total_sources,
                "source_title": title
            }
        )

        # 4. Emit thinking log
        word_count = len(content.split())
        thought = f"Source {source_index}: '{title[:30]}' [{credibility}] ~{word_count} words"
        await ws_manager.emit_thinking(report_id, "summary_agent", thought)
        state.add_thinking_log("summary_agent", thought)

        # Map credibility payload to dictionary expected by upsert_source_chunks
        credibility_payload = {
            "rating": source.get("credibility"),
            "score": source.get("credibility_score"),
            "label": source.get("credibility_label"),
            "emoji": source.get("credibility_icon")
        }

        # 5. Call upsert_source_chunks()
        chunks_stored = upsert_source_chunks(
            content=content,
            source_url=url,
            source_title=title,
            report_id=report_id,
            sub_question=sub_question,
            source_index=source_index,
            credibility=credibility_payload
        )

        # 6. If chunks_stored == 0
        if chunks_stored == 0:
            logger.warning(f"No chunks stored for {url}")
            return {
                "url": url,
                "chunks": 0,
                "status": "failed",
                "reason": "upsert returned 0"
            }

        # 7. Emit thinking log
        success_thought = f"Source {source_index}: stored {chunks_stored} chunks in Pinecone"
        await ws_manager.emit_thinking(report_id, "summary_agent", success_thought)
        state.add_thinking_log("summary_agent", success_thought)

        # 8. Log success
        logger.info(f"Stored {chunks_stored} chunks for {url}")

        # 9. Return success summary
        return {
            "url": url,
            "title": title,
            "chunks": chunks_stored,
            "status": "success",
            "credibility": credibility
        }

    except Exception as exc:
        logger.error(f"Error processing single source '{source.get('url')}': {exc}", exc_info=True)
        return {
            "url": source.get("url", ""),
            "chunks": 0,
            "status": "error",
            "reason": str(exc)
        }


async def embed_and_store(state: AgentMemory, report_id: str) -> Dict[str, Any]:
    """Flattens search results, chunks, embeds, and stores them in Pinecone.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        Summary dict containing success flags and chunk count.
    """
    try:
        # -- VALIDATE --
        search_results = validate_search_results(state)

        if not search_results:
            state.set_error("No search results to process")
            await ws_manager.emit_error(
                report_id, "summary_agent",
                "No sources to process"
            )
            return {
                "success": False,
                "total_chunks": 0
            }

        # -- FLATTEN SOURCES --
        all_sources = get_all_sources_flat(search_results)
        total_sources = len(all_sources)

        # -- START --
        await ws_manager.emit_agent_start(
            report_id, "summary_agent",
            f"Processing {total_sources} sources into searchable memory..."
        )

        state.add_log(
            "summary_agent", "start",
            f"Embedding {total_sources} sources into Pinecone"
        )

        # -- PROCESS EACH SOURCE --
        results = []
        total_chunks = 0
        failed_sources = 0

        for i, source in enumerate(all_sources, 1):
            result = await process_single_source(
                source=source,
                source_index=i,
                total_sources=total_sources,
                report_id=report_id,
                state=state
            )

            results.append(result)

            if result["status"] == "success":
                total_chunks += result["chunks"]
            else:
                failed_sources += 1

            # -- PROGRESS MILESTONES (25%, 50%, 75%) --
            percent = int((i / total_sources) * 100)
            if percent in [25, 50, 75]:
                await ws_manager.emit_agent_update(
                    report_id, "summary_agent",
                    f"Stored {total_chunks} chunks ({percent}% complete)",
                    data={
                        "chunks_stored": total_chunks,
                        "percent": percent
                    }
                )

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        # -- CHECK RESULTS --
        success_count = total_sources - failed_sources
        success_rate = success_count / total_sources if total_sources > 0 else 0.0

        if success_rate < 0.5:
            error_msg = f"Too many failures: only {success_count}/{total_sources} sources processed"
            state.set_error(error_msg)
            await ws_manager.emit_error(
                report_id, "summary_agent", error_msg
            )
            return {
                "success": False,
                "total_chunks": total_chunks
            }

        # -- STORE STATS IN STATE --
        chunk_stats = {
            "total_chunks_stored": total_chunks,
            "total_sources_processed": success_count,
            "failed_sources": failed_sources,
            "chunks_per_source": results
        }
        state.update_state("chunk_stats", chunk_stats)
        state.update_state("pinecone_ready", True)

        # -- LOG COMPLETION --
        avg_chunks = total_chunks / success_count if success_count > 0 else 0.0

        state.add_log(
            "summary_agent", "done",
            f"Stored {total_chunks} chunks from {success_count} sources"
        )

        state.add_thinking_log(
            "summary_agent",
            f"Pinecone now has {total_chunks} searchable chunks. Ready for retrieval."
        )

        # -- EMIT COMPLETION --
        await ws_manager.emit_agent_done(
            report_id, "summary_agent",
            f"Stored {total_chunks} chunks from {success_count} sources in memory",
            data={
                "total_chunks": total_chunks,
                "total_sources": success_count,
                "failed_sources": failed_sources,
                "avg_chunks_per_source": round(avg_chunks, 1)
            }
        )

        return {
            "success": True,
            "total_chunks": total_chunks,
            "total_sources": success_count,
            "failed_sources": failed_sources
        }

    except Exception as exc:
        error_msg = f"embed_and_store failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "summary_agent", error_msg)
        return {
            "success": False,
            "total_chunks": 0
        }


def get_embedding_stats(state: AgentMemory) -> Dict[str, Any]:
    """Retrieve embedding stats from memory and Pinecone index.

    Args:
        state: Agent memory context.

    Returns:
        Structured statistics mapping vector counts and ready flags.
    """
    try:
        chunk_stats = state.get_field("chunk_stats") or {}
        pinecone_stats = get_index_stats() or {}

        return {
            "state_chunks": chunk_stats.get("total_chunks_stored", 0),
            "pinecone_total_vectors": pinecone_stats.get("total_vectors", 0),
            "total_sources_processed": chunk_stats.get("total_sources_processed", 0),
            "failed_sources": chunk_stats.get("failed_sources", 0),
            "pinecone_status": pinecone_stats.get("status", "unknown"),
            "pinecone_ready": bool(state.get_field("pinecone_ready"))
        }
    except Exception as exc:
        logger.exception("Error retrieving embedding statistics")
        return {}


# ════════════════════════════════════════════
# PART 2: RETRIEVAL + SUMMARIZATION
# Added on Day 11
# Functions to be added:
#   - retrieve_chunks_for_question()
#   - summarize_with_gpt4o()
#   - generate_all_summaries()
#   - run() [main function called by pipeline]
# ════════════════════════════════════════════
