"""Manual End-to-End simulation script for Day 8.

This runs the start_research entry point directly and outputs the results,
including state logs, thinking logs, and summary statistics to the console.
"""

from __future__ import annotations

import os
import sys
import json
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

async def test_e2e():
    # Instead of HTTP request which requires active auth token,
    # we test the orchestrator agent and memory pipeline directly.
    from agents.orchestrator import start_research

    print("Starting research pipeline...")
    state = await start_research(
        report_id="e2e_test_001",
        topic="Benefits of meditation for mental health",
        depth="quick",
        language="english",
        user_id="test_user"
    )

    print("\n📊 PIPELINE RESULTS:")
    print(f"Status: {state.get_field('status')}")
    print("Questions generated:")
    for i, q in enumerate(state.get_field('sub_questions'), 1):
        print(f"  {i}. {q}")

    print("\nLogs:")
    for log in state.get_field('logs'):
        print(f"  [{log['agent']}] {log['message']}")

    print("\nThinking logs:")
    for t in state.get_field('thinking_logs'):
        print(f"  [{t['agent']}] {t['thought']}")

    stats = state.get_summary_stats()
    print(f"\nStats: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_e2e())
