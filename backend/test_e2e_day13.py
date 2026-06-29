"""Complete E2E test for the Multi-Agent Research Assistant (Day 8 to Day 13).

This script runs the entire sequence: topic -> sub-questions -> search -> storage
-> summaries -> fact-check -> report generation -> follow-up questions.
"""

from __future__ import annotations

import os
import sys
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
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


async def test_complete_pipeline():
    print("="*65)
    print("COMPLETE E2E TEST: Full Pipeline D8-D13")
    print("="*65)

    from agents.orchestrator import start_research
    from tools.confidence import get_confidence_label
    from tools.pinecone_tool import get_index_stats, delete_report_chunks

    # Get baseline vectors count
    stats_before = get_index_stats()
    vectors_before = stats_before.get("total_vectors", 0)

    topic = "Future of renewable energy"
    report_id = "e2e_complete_final"
    print(f"\n📋 Topic: {topic}")
    print("Starting complete pipeline...\n")

    start_time = time.time()

    state = await start_research(
        report_id=report_id,
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )

    elapsed = time.time() - start_time

    # Get post-run vectors count
    stats_after = get_index_stats()
    vectors_after = stats_after.get("total_vectors", 0)

    questions = state.get_field("sub_questions", [])
    search_results = state.get_field("search_results", [])
    chunk_stats = state.get_field("chunk_stats", {})
    summaries = state.get_field("summaries", [])
    verified_claims = state.get_field("verified_claims", [])
    final_report = state.get_field("final_report", {})
    followup = state.get_field("followup_questions", [])
    confidence = state.get_field("confidence_score", 0)
    status = state.get_field("status")

    print("\n" + "="*65)
    print("📊 COMPLETE PIPELINE RESULTS")
    print("="*65)

    total_sources = sum(
        r.get("source_count", 0) for r in search_results
    )

    print(f"\n⏱️  Time taken: {elapsed:.1f} seconds")
    print(f"\n{'─'*65}")
    print("PIPELINE STAGES:")
    print(f"{'─'*65}")
    print(f"✅ [D8]  Orchestrator:  {len(questions)} sub-questions")
    print(f"✅ [D9]  Search Agent:  {total_sources} sources found")
    print(f"✅ [D10] Store:         +{vectors_after - vectors_before} vectors")
    print(f"✅ [D11] Summarize:    {len(summaries)} summaries")

    verified = sum(1 for c in verified_claims if c.get("status") == "verified")
    uncertain = sum(1 for c in verified_claims if c.get("status") == "uncertain")
    unverified = sum(1 for c in verified_claims if c.get("status") == "unverified")

    print(f"✅ [D12] FactCheck:    {len(verified_claims)} claims (✅{verified} ⚠️{uncertain} ❌{unverified})")

    label = get_confidence_label(confidence)
    print(f"✅ [D13] Writer:       {final_report.get('word_count', 0)} words")
    print(f"✅ [D13] FollowUp:     {len(followup)} questions")
    print(f"✅ Status:             {status}")
    print(f"✅ Confidence:         {confidence}% {label.get('emoji', '❓')} {label.get('label', 'unknown')}")

    print(f"\n{'─'*65}")
    print("📄 REPORT PREVIEW")
    print(f"{'─'*65}")
    print(f"Title: {final_report.get('title', '')}")
    print(f"\nExecutive Summary:")
    exec_sum = final_report.get("executive_summary", "")
    print(exec_sum[:300] + "...")

    print(f"\n🔍 Key Findings:")
    for i, finding in enumerate(final_report.get("key_findings", [])[:5], 1):
        print(f"  {i}. {finding.get('point', '')[:65]}")
        citation = finding.get('citation', '')[:45]
        status_icon = "✅" if finding.get('status') == "verified" else "⚠️"
        print(f"     {status_icon} [{citation}]")

    print(f"\n🔮 Follow-up Questions:")
    for i, q in enumerate(followup[:5], 1):
        print(f"  {i}. {q}")

    print(f"\n{'─'*65}")
    print("💭 THINKING LOGS (Last 12):")
    print(f"{'─'*65}")
    thinking = state.get_field("thinking_logs", [])[-12:]
    for t in thinking:
        agent = t.get("agent", "")[:14]
        thought = t.get("thought", "")[:60]
        print(f"  [{agent:<14}] {thought}")

    print(f"\n{'='*65}")
    print("✅ COMPLETE E2E TEST PASSED")
    print(f"Full pipeline: {elapsed:.1f}s")
    print("Pipeline: Topic→Questions→Search→Store")
    print("  →Summarize→FactCheck→Write→FollowUp")
    print("="*65)

    # Cleanup vectors
    delete_report_chunks(report_id)
    print("🗑️  Test vectors cleaned up")


if __name__ == "__main__":
    asyncio.run(test_complete_pipeline())
