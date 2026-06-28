"""Manual E2E simulation script for Day 8 + Day 9 + Day 10 + Day 11 + Day 12.

This script executes the entire pipeline (Orchestration -> Search -> Summary -> FactCheck)
and displays detailed verification outcomes, confidence scores, and reasoning logs.
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
    print("E2E TEST: Day 8-12 Complete Pipeline")
    print("="*60)

    from agents.orchestrator import start_research
    from agents.factcheck_agent import (
        get_factcheck_summary,
        get_verified_only,
        calculate_verification_stats
    )
    from tools.confidence import get_confidence_label

    topic = "Benefits of meditation for stress"
    print(f"\n📋 Topic: {topic}\n")

    state = await start_research(
        report_id="e2e_d12_final",
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )

    questions = state.get_field("sub_questions") or []
    summaries = state.get_field("summaries") or []
    all_claims = state.get_field("verified_claims") or []
    confidence = state.get_field("confidence_score", 0)

    print("─"*60)
    print("📊 COMPLETE PIPELINE RESULTS:")
    print("─"*60)
    print(f"✅ Questions:     {len(questions)}")

    total_sources = sum(
        r.get("source_count", 0)
        for r in state.get_field("search_results", [])
    )
    chunk_stats = state.get_field("chunk_stats") or {}

    print(f"✅ Sources:       {total_sources}")
    print(f"✅ Chunks stored: {chunk_stats.get('total_chunks_stored', 0)}")
    print(f"✅ Summaries:     {len(summaries)}")
    print(f"✅ Total claims:  {len(all_claims)}")

    if all_claims:
        stats = calculate_verification_stats(all_claims)
        print(f"   ✅ Verified:   {stats['verified']}")
        print(f"   ⚠️  Uncertain:  {stats['uncertain']}")
        print(f"   ❌ Unverified: {stats['unverified']}")

    print(f"✅ Confidence:    {confidence}%")

    label = get_confidence_label(confidence)
    print(f"   {label['emoji']} {label['label']}")
    print(f"   {label['description']}")

    print("\n" + "─"*60)
    print("🔍 VERIFIED CLAIMS (top 5):")
    print("─"*60)
    verified_only = get_verified_only(state)
    for i, claim in enumerate(verified_only[:5], 1):
        sources = len(claim['supporting_sources'])
        print(f"\n{i}. {claim['claim']}")
        print(f"   Status: ✅ {claim['status']}")
        print(f"   Sources: {sources}")
        for src in claim['supporting_sources'][:2]:
            print(f"   → {src[:55]}")

    removed = [c for c in all_claims if c["status"] == "unverified"]
    if removed:
        print(f"\n❌ REMOVED CLAIMS ({len(removed)}):")
        for c in removed[:3]:
            print(f"  • {c['claim'][:60]}")

    print("\n" + "─"*60)
    print("💭 THINKING LOGS (Last 10):")
    print("─"*60)
    thinking = state.get_field("thinking_logs", [])[-10:]
    for t in thinking:
        agent = t.get("agent", "")[:12]
        thought = t.get("thought", "")[:65]
        print(f"  [{agent}] {thought}")

    print("\n" + "="*60)
    print("✅ E2E TEST COMPLETE")
    print("Pipeline: Topic → Questions → Search")
    print("  → Store → Summarize → FactCheck")
    print(f"Confidence Score: {confidence}%")
    print("Ready for Day 13: Writer + FollowUp")
    print("="*60)

    # Cleanup
    from tools.pinecone_tool import delete_report_chunks
    delete_report_chunks("e2e_d12_final")
    print("🗑️  Test vectors cleaned up")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
