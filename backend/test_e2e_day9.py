"""Manual E2E simulation script for Day 8 + Day 9.

This script executes the entire pipeline (Orchestration + Search)
and displays detailed question generation, web search results,
credibility summaries, and agent logs.
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
    print("\n" + "="*50)
    print("E2E TEST: Day 8 + Day 9 Pipeline")
    print("="*50)

    from agents.orchestrator import start_research

    topic = "Impact of social media on mental health"

    print(f"\n📋 Topic: {topic}")
    print("Starting pipeline...\n")

    state = await start_research(
        report_id="e2e_d9_test",
        topic=topic,
        depth="deep",
        language="english",
        user_id="test_user"
    )

    print("\n" + "─"*50)
    print("ORCHESTRATOR RESULTS:")
    print("─"*50)
    questions = state.get_field("sub_questions")
    for i, q in enumerate(questions, 1):
        print(f"Q{i}: {q}")

    print("\n" + "─"*50)
    print("SEARCH AGENT RESULTS:")
    print("─"*50)
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

    print("\n" + "─"*50)
    print("PIPELINE SUMMARY:")
    print("─"*50)
    stats = state.get_summary_stats()
    print(f"Status:          {state.get_field('status')}")
    print(f"Sub-questions:   {len(questions)}")
    print(f"Total sources:   {total_sources}")
    print(f"Current agent:   {state.get_field('current_agent')}")
    print(f"Logs:            {len(state.get_field('logs'))}")
    print(f"Thinking logs:   {len(state.get_field('thinking_logs'))}")

    print("\n" + "─"*50)
    print("THINKING LOGS (Agent Reasoning):")
    print("─"*50)
    for t in state.get_field("thinking_logs"):
        agent = t.get("agent", "")
        thought = t.get("thought", "")[:70]
        print(f"[{agent}] {thought}")

    print("\n" + "="*50)
    print("✅ E2E TEST PASSED")
    print(f"Total sources found: {total_sources}")
    print("Ready for Day 10: Summary Agent")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
