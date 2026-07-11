"""Summary Agent for the Multi-Agent Research Assistant.

This agent handles flattening raw search results, dividing source content
into overlapping text segments (chunks), generating embedding vectors, and
storing them in the Pinecone vector database.
"""

from __future__ import annotations

import asyncio
import logging
import time
import os
import re
from typing import List, Dict, Any, Optional

from openai import OpenAI
from tools.pinecone_tool import (
    upsert_source_chunks,
    chunk_text,
    get_index_stats,
    delete_report_chunks
)
from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager
from utils.translator import (
    get_language_prompt,
    get_report_labels
)

logger = logging.getLogger(__name__)

# Alias to satisfy the Day 10 naming specification
chunk_content = chunk_text

_openai_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Retrieve singleton OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")
        cleaned_key = api_key.strip().strip('"').strip("'")
        _openai_client = OpenAI(api_key=cleaned_key)
    return _openai_client




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
        chunks_stored = await upsert_source_chunks(
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

        # -- PROCESS SOURCES IN PARALLEL --
        # Limit concurrent embedding calls to 5
        semaphore = asyncio.Semaphore(5)
        completed_count = 0
        total_chunks = 0
        failed_sources = 0

        async def embed_with_semaphore(source, index, total):
            nonlocal completed_count
            async with semaphore:
                res = await process_single_source(
                    source=source,
                    source_index=index,
                    total_sources=total,
                    report_id=report_id,
                    state=state
                )
                completed_count += 1
                percent = int((completed_count / total) * 100)
                if percent in [25, 50, 75]:
                    await ws_manager.emit_agent_update(
                        report_id, "summary_agent",
                        f"Stored chunks ({percent}% complete)",
                        data={
                            "percent": percent
                        }
                    )
                return res

        embed_tasks = [
            embed_with_semaphore(source=source, index=i+1, total=total_sources)
            for i, source in enumerate(all_sources)
        ]

        raw_results = await asyncio.gather(*embed_tasks, return_exceptions=True)
        results = []

        for result in raw_results:
            if isinstance(result, Exception):
                logger.error(f"Embedding error: {result}")
                failed_sources += 1
            elif result is not None:
                results.append(result)
                if result.get("status") == "success":
                    total_chunks += result.get("chunks", 0)
                else:
                    failed_sources += 1
            else:
                failed_sources += 1


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
# ════════════════════════════════════════════

async def retrieve_chunks_for_question(
    question: str,
    report_id: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Retrieve the most relevant document chunks from Pinecone for a question.

    Args:
        question: The search query/question.
        report_id: The active report execution ID.
        top_k: The number of top relevant chunks to fetch.

    Returns:
        List of matching chunk dictionaries.
    """
    from tools.pinecone_tool import query_relevant_chunks
    try:
        logger.info(f"Querying Pinecone for: {question[:50]}")
        chunks = await query_relevant_chunks(
            question=question,
            report_id=report_id,
            top_k=top_k
        )

        if not chunks:
            logger.warning(f"No chunks found for: {question}")
            return []

        # Sort by score descending (highest relevance first)
        chunks_sorted = sorted(
            chunks,
            key=lambda x: x.get("score", 0.0),
            reverse=True
        )

        logger.info(f"Retrieved {len(chunks_sorted)} chunks, best score: {chunks_sorted[0].get('score', 0.0)}")
        return chunks_sorted
    except Exception as exc:
        logger.error(f"Error querying Pinecone for question '{question[:40]}': {exc}", exc_info=True)
        return []


def build_context_from_chunks(
    chunks: List[Dict[str, Any]],
    question: str
) -> tuple[str, List[str]]:
    """Build a formatted context block and extract a list of unique source URLs.

    Args:
        chunks: List of relevant chunks retrieved from Pinecone.
        question: The sub-question context.

    Returns:
        A tuple of (formatted context string, list of deduplicated source URLs).
    """
    if not chunks:
        return "No relevant sources found.", []

    context_parts = []
    citation_urls = []
    seen_urls = set()

    icons = {
        "academic": "🎓",
        "news": "📰",
        "blog": "✍️",
        "government": "🏛️",
        "unknown": "❓"
    }

    for i, chunk in enumerate(chunks, 1):
        url = chunk.get("source_url", "")
        title = chunk.get("source_title", "Unknown")
        content = chunk.get("content", "")
        credibility = chunk.get("credibility", "unknown")
        if isinstance(credibility, dict):
            credibility = credibility.get("rating", "unknown")
        score = chunk.get("score", 0.0)

        icon = icons.get(str(credibility).lower(), "❓")

        source_block = f"""
[Source {i} - {icon} {title}]
URL: {url}
Relevance Score: {score:.2f}
Content: {content}
─────────────────────
"""
        context_parts.append(source_block)

        if url and url not in seen_urls:
            citation_urls.append(url)
            seen_urls.add(url)

    full_context = "\n".join(context_parts)
    return full_context, citation_urls


def build_summary_prompt(
    question: str,
    context: str,
    language: str
) -> tuple[str, str]:
    """Build the system and user prompts for GPT-4o-mini.

    Args:
        question: Research sub-question.
        context: Formatted context blocks.
        language: Report language.

    Returns:
        A tuple of (system_prompt, user_prompt).
    """
    language_instruction = get_language_prompt(language)

    system_prompt = """You are a precise research analyst and academic writer. Your job is to answer research questions using ONLY the provided source materials.

STRICT RULES:
1. Use ONLY information from provided sources
2. NEVER make up facts or statistics
3. Cite every fact with [Source: URL]
4. If sources conflict, acknowledge both views
5. If sources don't answer the question, say "Available sources do not directly address this aspect"
6. Be specific: include numbers, dates, names when available in sources
7. Length: 150-250 words
8. Do not include generic statements that aren't from the sources"""

    user_prompt = f"""Research Question:
{question}

Source Materials:
{context}

Instructions:
- Answer the research question directly using the source materials above
- Cite every factual claim: [Source: URL]
- Include specific statistics and data from the sources
- If multiple sources support a claim, cite all of them
- {language_instruction}

Write the summary now:"""

    return system_prompt, user_prompt


def extract_citations_from_summary(
    summary_text: str,
    available_urls: List[str]
) -> List[str]:
    """Extract and validate citation URLs from the generated summary.

    Args:
        summary_text: The LLM generated summary.
        available_urls: The list of candidate URLs present in the context.

    Returns:
        List of unique, verified citation URLs.
    """
    if not summary_text:
        return []

    # Method 1: Extract [Source: URL] patterns
    pattern = r'\[Source:\s*(https?://[^\]\s]+)\]'
    found = re.findall(pattern, summary_text)

    # Method 2: Also check for plain URLs in text
    url_pattern = r'https?://[^\s\])]+'
    plain_urls = re.findall(url_pattern, summary_text)
    found.extend(plain_urls)

    # Validate URLs (partial match allowed)
    valid_citations = []
    for url in found:
        url_clean = url.strip().rstrip(".,;:")
        for avail_url in available_urls:
            if url_clean in avail_url or avail_url in url_clean:
                if avail_url not in valid_citations:
                    valid_citations.append(avail_url)
                break

    # Deduplicate keeping order
    unique_citations = list(dict.fromkeys(valid_citations))

    # Fallback to available_urls if no citations found in text
    if not unique_citations and available_urls:
        logger.warning("No explicit citations found in summary text. Falling back to all available context URLs.")
        unique_citations = list(available_urls)

    return unique_citations


async def summarize_single_question(
    question: str,
    question_index: int,
    total_questions: int,
    report_id: str,
    language: str,
    state: AgentMemory
) -> Dict[str, Any] | None:
    """Run the complete retrieval, context generation, and completion pipeline for one question.

    Args:
        question: Sub-question string.
        question_index: Index representing the current sub-question.
        total_questions: Total number of sub-questions.
        report_id: Unique string identifying the active report.
        language: Report output language.
        state: Agent memory context.

    Returns:
        A dictionary summarizing the result of this question's processing, or None.
    """
    try:
        # Emit progress
        await ws_manager.emit_agent_update(
            report_id, "summary_agent",
            f"Summarizing Q{question_index}/{total_questions}: {question[:55]}...",
            data={
                "current": question_index,
                "total": total_questions
            }
        )

        # Retrieve chunks
        chunks = await retrieve_chunks_for_question(
            question=question,
            report_id=report_id,
            top_k=5
        )

        if not chunks:
            warn_msg = f"Q{question_index}: no relevant chunks found in Pinecone"
            logger.warning(warn_msg)
            await ws_manager.emit_thinking(report_id, "summary_agent", warn_msg)

            return {
                "question": question,
                "summary": f"Insufficient source material found for: {question}",
                "citations": [],
                "chunk_count": 0,
                "avg_relevance_score": 0.0,
                "word_count": 0,
                "language": language,
                "status": "no_chunks"
            }

        # Emit thinking
        avg_score = sum(c.get("score", 0.0) for c in chunks) / len(chunks)
        await ws_manager.emit_thinking(
            report_id, "summary_agent",
            f"Q{question_index}: retrieved {len(chunks)} chunks, avg relevance: {avg_score:.2f}"
        )

        # Build context
        context, available_urls = build_context_from_chunks(chunks, question)

        # Build prompt
        system_prompt, user_prompt = build_summary_prompt(question, context, language)

        # Call OpenAI with retries
        client = get_openai_client()
        summary_text = None

        for attempt in range(3):
            try:
                logger.info(f"Generating summary for Q{question_index} (attempt {attempt + 1}/3)...")
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=500,
                    temperature=0.3
                )
                summary_text = response.choices[0].message.content
                if summary_text and summary_text.strip():
                    summary_text = summary_text.strip()
                    break
                else:
                    raise ValueError("Received empty content from completion.")
            except Exception as e:
                logger.warning(f"Summarization attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    raise

        if not summary_text:
            return None

        # Extract citations
        citations = extract_citations_from_summary(summary_text, available_urls)

        # Stats
        word_count = len(summary_text.split())
        citation_count = len(citations)

        # Emit thinking
        await ws_manager.emit_thinking(
            report_id, "summary_agent",
            f"Q{question_index}: summary generated, {word_count} words, {citation_count} citations found"
        )

        state.add_thinking_log(
            "summary_agent",
            f"Q{question_index} summary: {word_count} words, citations: {citation_count}"
        )

        return {
            "question": question,
            "summary": summary_text,
            "citations": citations,
            "chunk_count": len(chunks),
            "avg_relevance_score": round(avg_score, 3),
            "word_count": word_count,
            "language": language,
            "status": "success"
        }

    except Exception as exc:
        error_msg = f"Summary failed for Q{question_index}: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        await ws_manager.emit_thinking(
            report_id, "summary_agent",
            f"Q{question_index}: summarization failed"
        )
        return None


async def retrieve_and_summarize(
    state: AgentMemory,
    report_id: str
) -> Dict[str, Any]:
    """Retrieve relevant chunks and generate summaries for all sub-questions.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        Summary dict containing success flags and generated summaries.
    """
    try:
        # Validate Pinecone ready
        pinecone_ready = state.get_field("pinecone_ready", False)
        if not pinecone_ready:
            error = "Pinecone not ready. Run embed_and_store first."
            state.set_error(error)
            await ws_manager.emit_error(report_id, "summary_agent", error)
            return {"success": False, "summaries": []}

        # Get questions & language
        sub_questions = state.get_field("sub_questions", [])
        language = state.get_field("language", "english")

        if not sub_questions:
            error = "No sub-questions to summarize"
            state.set_error(error)
            await ws_manager.emit_error(report_id, "summary_agent", error)
            return {"success": False, "summaries": []}

        total = len(sub_questions)

        await ws_manager.emit_agent_update(
            report_id, "summary_agent",
            f"Retrieving and summarizing {total} questions..."
        )

        state.add_log(
            "summary_agent", "start",
            f"Starting RAG summarization for {total} questions"
        )

        # Wait for Pinecone to fully index vectors
        await asyncio.sleep(2)

        # -- SUMMARIZE QUESTIONS IN PARALLEL --
        # Limit concurrent GPT-4o calls to 3
        semaphore = asyncio.Semaphore(3)

        async def summarize_with_semaphore(question, index):
            async with semaphore:
                return await summarize_single_question(
                    question=question,
                    question_index=index,
                    total_questions=total,
                    report_id=report_id,
                    language=language,
                    state=state
                )

        summarize_tasks = [
            summarize_with_semaphore(question=q, index=i+1)
            for i, q in enumerate(sub_questions)
        ]

        raw_summaries = await asyncio.gather(*summarize_tasks, return_exceptions=True)
        summaries = []
        failed_count = 0

        for i, result in enumerate(raw_summaries):
            if isinstance(result, Exception):
                logger.error(f"Summarize error for Q{i+1}: {result}")
                failed_count += 1
            elif result is not None:
                summaries.append(result)
                if result.get("status") != "success":
                    failed_count += 1
            else:
                failed_count += 1


        if not summaries:
            error = "All summarizations failed"
            state.set_error(error)
            await ws_manager.emit_error(report_id, "summary_agent", error)
            return {"success": False, "summaries": []}

        # Store in state
        state.update_state("summaries", summaries)

        # Stats
        total_citations = sum(len(s.get("citations", [])) for s in summaries)
        successful = [s for s in summaries if s.get("status") == "success"]
        avg_chunks = (
            sum(s.get("chunk_count", 0) for s in successful) / len(successful)
            if successful else 0.0
        )

        # Log completion
        state.add_log(
            "summary_agent", "done",
            f"Generated {len(summaries)} summaries with {total_citations} total citations"
        )
        state.add_thinking_log(
            "summary_agent",
            f"All summaries complete. {len(successful)}/{total} successful, {total_citations} citations found"
        )

        await ws_manager.emit_agent_done(
            report_id, "summary_agent",
            f"Generated {len(successful)} summaries with {total_citations} citations",
            data={
                "summaries_count": len(successful),
                "total_citations": total_citations,
                "avg_chunks_per_summary": round(avg_chunks, 1),
                "language": language,
                "failed": failed_count
            }
        )

        return {
            "success": True,
            "summaries": summaries,
            "total_citations": total_citations
        }

    except Exception as exc:
        error_msg = f"retrieve_and_summarize failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "summary_agent", error_msg)
        return {"success": False, "summaries": []}


async def run(
    state: AgentMemory,
    report_id: str
) -> bool:
    """Entry point for the summary agent called by orchestrator.

    Runs embed_and_store (Part 1) and retrieve_and_summarize (Part 2) in sequence.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        True if execution completed successfully, else False.
    """
    try:
        state.set_current_agent("summary_agent")

        logger.info("Summary Agent starting Part 1...")
        embed_result = await embed_and_store(state, report_id)

        if not embed_result.get("success"):
            logger.error("Summary Agent Part 1 failed")
            return False

        logger.info(f"Part 1 done: {embed_result.get('total_chunks', 0)} chunks stored")

        # Wait for Pinecone indexing
        await asyncio.sleep(2)

        logger.info("Summary Agent starting Part 2...")
        summary_result = await retrieve_and_summarize(state, report_id)

        if not summary_result.get("success"):
            logger.error("Summary Agent Part 2 failed")
            return False

        logger.info(f"Part 2 done: {len(summary_result.get('summaries', []))} summaries generated")

        # Hand off to FactCheck Agent
        state.set_current_agent("factcheck_agent")
        return True

    except Exception as exc:
        error_msg = f"Summary Agent run() failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "summary_agent", error_msg)
        return False
