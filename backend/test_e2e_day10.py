"""Manual E2E simulation script for Day 8 + Day 9 + Day 10.

This script executes the entire pipeline (Orchestration + Search + Summary Agent Part 1)
and displays detailed question generation, web search results,
credibility summaries, chunks stored in Pinecone, and Pinecone vector count changes.
"""

from __future__ import annotations

import os
import sys
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

# Setup paths to allow local imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from tools.pinecone_tool import get_index_stats, delete_report_chunks
from agents.orchestrator import start_research


async def test_full_pipeline():
    print("\n" + "="*55)
    print("E2E TEST: Day 8 + Day 9 + Day 10 Part 1 Pipeline")
    print("="*55)

    # 1. Check initial index status
    initial_stats = get_index_stats()
    initial_vectors = initial_stats.get("total_vectors", 0)
    print(f"\n📡 Initial Pinecone Index: {initial_stats.get('index_name')}")
    print(f"   Status: {initial_stats.get('status')}")
    print(f"   Initial Vectors Count: {initial_vectors}")

    topic = "Future of quantum computing"
    report_id = f"e2e_d10_test_{int(time.time())}"

    print(f"\n📋 Topic: {topic}")
    print(f"🆔 Report ID: {report_id}")
    print("Starting pipeline...\n")

    # 2. Run start_research
    state = await start_research(
        report_id=report_id,
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )

    print("\n" + "─"*55)
    print("ORCHESTRATOR RESULTS:")
    print("─"*55)
    questions = state.get_field("sub_questions")
    for i, q in enumerate(questions, 1):
        print(f"Q{i}: {q}")

    print("\n" + "─"*55)
    print("SEARCH AGENT RESULTS:")
    print("─"*55)
    search_results = state.get_field("search_results")
    total_sources = 0
    for result in search_results:
        q_short = result["question"][:55]
        count = result["source_count"]
        avg_cred = result["avg_credibility_score"]
        total_sources += count
        print(f"\n📌 {q_short}...")
        print(f"   Sources: {count} | Avg Credibility: {avg_cred}/100")
        for src in result["sources"]:
            icon = src.get("credibility_icon", "❓")
            title = src.get("title", "")[:45]
            cred = src.get("credibility", "unknown")
            print(f"   {icon} {title} [{cred}]")

    print("\n" + "─"*55)
    print("SUMMARY AGENT PART 1 RESULTS:")
    print("─"*55)
    chunk_stats = state.get_field("chunk_stats") or {}
    total_chunks_stored = chunk_stats.get("total_chunks_stored", 0)
    print(f"Total Sources Processed: {chunk_stats.get('total_sources_processed', 0)}")
    print(f"Total Chunks Stored:    {total_chunks_stored}")
    print(f"Pinecone Ready:         {state.get_field('pinecone_ready')}")

    # 3. Check final index status
    final_stats = get_index_stats()
    final_vectors = final_stats.get("total_vectors", 0)
    print(f"\n📡 Final Pinecone Index State:")
    print(f"   Status: {final_stats.get('status')}")
    print(f"   Final Vectors Count: {final_vectors}")
    print(f"   Net Vectors Added:   {final_vectors - initial_vectors}")

    print("\n" + "─"*55)
    print("PIPELINE SUMMARY:")
    print("─"*55)
    print(f"Status:          {state.get_field('status')}")
    print(f"Sub-questions:   {len(questions)}")
    print(f"Total sources:   {total_sources}")
    print(f"Current agent:   {state.get_field('current_agent')}")
    print(f"Logs:            {len(state.get_field('logs'))}")
    print(f"Thinking logs:   {len(state.get_field('thinking_logs'))}")

    print("\n" + "─"*55)
    print("THINKING LOGS (Agent Reasoning):")
    print("─"*55)
    for t in state.get_field("thinking_logs"):
        agent = t.get("agent", "")
        thought = t.get("thought", "")[:75]
        print(f"[{agent}] {thought}")

    print("\n" + "─"*55)
    print("CLEANING UP TEST VECTORS...")
    print("─"*55)
    cleanup_success = delete_report_chunks(report_id)
    if cleanup_success:
        print("✅ Cleaned up temporary report chunks from Pinecone.")
    else:
        print("❌ Failed to clean up chunks from Pinecone.")

    post_cleanup_stats = get_index_stats()
    print(f"   Post-Cleanup Vectors Count: {post_cleanup_stats.get('total_vectors', 0)}")

    print("\n" + "="*55)
    print("✅ E2E TEST COMPLETE")
    print(f"Total sources found: {total_sources}")
    print(f"Total chunks stored: {total_chunks_stored}")
    print("="*55)


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
