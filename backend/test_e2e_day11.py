"""Manual E2E simulation script for Day 8 + Day 9 + Day 10 + Day 11.

This script executes the entire pipeline (Orchestration -> Search -> Summary Agent Full)
and displays detailed results, including generated summaries, citations, and thinking logs.
"""

from __future__ import annotations

import os
import sys
import asyncio
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


async def test_full_pipeline():
    print("="*60)
    print("E2E TEST: Day 8+9+10+11 Complete Pipeline")
    print("="*60)

    from agents.orchestrator import start_research
    from tools.pinecone_tool import get_index_stats, delete_report_chunks

    vectors_before = get_index_stats().get("total_vectors", 0)

    topic = "Benefits of regular exercise"
    print(f"\n📋 Topic: {topic}\n")

    state = await start_research(
        report_id="e2e_d11_final",
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )

    vectors_after = get_index_stats().get("total_vectors", 0)

    questions = state.get_field("sub_questions") or []
    search_results = state.get_field("search_results") or []
    chunk_stats = state.get_field("chunk_stats") or {}
    summaries = state.get_field("summaries") or []

    print("─"*60)
    print("📊 PIPELINE RESULTS:")
    print("─"*60)
    print(f"✅ Questions:   {len(questions)}")

    total_sources = sum(
        r.get("source_count", 0)
        for r in search_results
    )
    print(f"✅ Sources:     {total_sources}")
    print(f"✅ Chunks:      {chunk_stats.get('total_chunks_stored', 0)}")
    print(f"✅ New vectors: +{vectors_after - vectors_before}")
    print(f"✅ Summaries:   {len(summaries)}")

    if summaries:
        total_cit = sum(
            len(s.get("citations", []))
            for s in summaries
        )
        print(f"✅ Citations:   {total_cit}")

    print("\n" + "─"*60)
    print("📝 GENERATED SUMMARIES:")
    print("─"*60)

    for i, summary in enumerate(summaries, 1):
        print(f"\n{'─'*40}")
        print(f"Q{i}: {summary['question']}")
        print(f"{'─'*40}")
        print(f"{summary['summary'][:300]}...")
        print(f"\n📎 Citations ({len(summary['citations'])}):")
        for cite in summary["citations"]:
            print(f"   • {cite[:60]}")
        print(f"📊 Chunks used: {summary['chunk_count']}")
        print(f"📊 Words: {summary['word_count']}")

    print("\n" + "─"*60)
    print("💭 THINKING LOGS (Last 8):")
    print("─"*60)
    thinking = state.get_field("thinking_logs")[-8:]
    for t in thinking:
        agent = t.get("agent", "")[:12]
        thought = t.get("thought", "")[:65]
        print(f"  [{agent}] {thought}")

    print("\n" + "="*60)
    print("✅ E2E TEST COMPLETE")
    print("Pipeline: Topic → Questions → Search")
    print("         → Store → Retrieve → Summarize")
    print("Ready for Day 12: FactCheck Agent")
    print("="*60)

    # Cleanup
    delete_report_chunks("e2e_d11_final")
    print("🗑️  Test vectors cleaned up")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
