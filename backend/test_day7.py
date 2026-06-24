"""Standalone validation script for Day 7 (AgentState, Memory, and WebSockets).

Run this from the repository root with:

    backend/venv/Scripts/python backend/test_day7.py
"""

from __future__ import annotations

import os
import sys
# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import time
from pathlib import Path
from dotenv import load_dotenv

# Set project root in path to allow imports of backend packages
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load backend's local environment file
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from backend.memory.agent_memory import AgentMemory
from backend.utils.websocket_manager import WebSocketManager
from backend.utils.translator import (
    validate_language,
    get_language_prompt,
    get_report_labels,
    get_all_languages
)


def main() -> None:
    """Run all 14 test cases verifying AgentMemory, WebSocketManager, and Translator."""
    print("=" * 60)
    print("RUNNING DAY 7 VALIDATION TEST SUITE")
    print("=" * 60)

    # ----------------------------------------------------
    # Test 1: AgentMemory Initialization
    # ----------------------------------------------------
    mem = AgentMemory(
        report_id="test123",
        topic="AI topic",
        depth="deep",
        language="english",
        user_id="user1"
    )
    state = mem.to_dict()
    assert state["report_id"] == "test123"
    assert state["topic"] == "AI topic"
    assert state["depth"] == "deep"
    assert state["language"] == "english"
    assert state["user_id"] == "user1"
    assert state["status"] == "pending"
    assert state["sub_questions"] == []
    assert state["confidence_score"] == 0
    assert state["current_agent"] is None
    assert state["error"] is None
    print("✅ Test 1: Initialization PASSED")

    # ----------------------------------------------------
    # Test 2: update_state()
    # ----------------------------------------------------
    assert mem.update_state("status", "running") is True
    assert mem.get_field("status") == "running"
    assert mem.update_state("confidence_score", 75) is True
    assert mem.get_field("confidence_score") == 75
    
    # Try updating invalid field
    assert mem.update_state("fake_field", "value") is False
    print("✅ Test 2: update_state PASSED")

    # ----------------------------------------------------
    # Test 3: update_multiple()
    # ----------------------------------------------------
    updates = {
        "topic": "New AI Topic",
        "depth": "expert",
        "language": "spanish"
    }
    results = mem.update_multiple(updates)
    assert all(results.values()) is True
    assert mem.get_field("topic") == "New AI Topic"
    assert mem.get_field("depth") == "expert"
    assert mem.get_field("language") == "spanish"
    print("✅ Test 3: update_multiple PASSED")

    # ----------------------------------------------------
    # Test 4: add_log()
    # ----------------------------------------------------
    mem.add_log("orchestrator", "running", "Orchestrating questions")
    mem.add_log("search_agent", "running", "Web searches in progress")
    mem.add_log("writer", "done", "Report composed")
    
    logs = mem.get_field("logs")
    assert len(logs) == 3
    for log in logs:
        assert "agent" in log
        assert "status" in log
        assert "message" in log
        assert "timestamp" in log
        assert isinstance(log["timestamp"], int)
        # Verify timestamp is recent (within 5 seconds)
        assert abs(time.time() - log["timestamp"]) < 5.0
    print("✅ Test 4: add_log PASSED")

    # ----------------------------------------------------
    # Test 5: add_thinking_log()
    # ----------------------------------------------------
    mem.add_thinking_log("orchestrator", "Parsing broad user prompt")
    mem.add_thinking_log("search_agent", "Submitting 4 queries to Tavily")
    
    t_logs = mem.get_field("thinking_logs")
    assert len(t_logs) == 2
    for t_log in t_logs:
        assert "agent" in t_log
        assert "thought" in t_log
        assert "timestamp" in t_log
        assert isinstance(t_log["timestamp"], int)
    print("✅ Test 5: add_thinking_log PASSED")

    # ----------------------------------------------------
    # Test 6: append_to_field()
    # ----------------------------------------------------
    assert mem.append_to_field("sub_questions", "What is AI?") is True
    assert "What is AI?" in mem.get_field("sub_questions")
    
    # Try appending to non-list field
    assert mem.append_to_field("topic", "Invalid append") is False
    print("✅ Test 6: append_to_field PASSED")

    # ----------------------------------------------------
    # Test 7: set_status()
    # ----------------------------------------------------
    mem.set_status("running")
    assert mem.get_field("status") == "running"
    mem.set_status("done")
    assert mem.get_field("status") == "done"
    
    # Try setting invalid status
    mem.set_status("flying")
    assert mem.get_field("status") == "done"
    print("✅ Test 7: set_status PASSED")

    # ----------------------------------------------------
    # Test 8: set_error()
    # ----------------------------------------------------
    mem.set_error("Tavily failed")
    assert mem.get_field("error") == "Tavily failed"
    assert mem.get_field("status") == "failed"
    print("✅ Test 8: set_error PASSED")

    # ----------------------------------------------------
    # Test 9: get_state() returns copy
    # ----------------------------------------------------
    state_copy = mem.get_state()
    state_copy["topic"] = "Malicious Modification"
    assert mem.get_field("topic") != "Malicious Modification"
    print("✅ Test 9: get_state copy PASSED")

    # ----------------------------------------------------
    # Test 10: get_summary_stats()
    # ----------------------------------------------------
    mem.reset_state()
    mem.update_state("sub_questions", ["Q1", "Q2"])
    
    # Add dummy search result
    mem.update_state("search_results", [
        {
            "question": "Q1",
            "sources": [
                {"url": "https://nature.com", "title": "Nature Paper"}
            ]
        }
    ])
    
    # Add dummy summary
    mem.update_state("summaries", [
        {"question": "Q1", "chunk_count": 10}
    ])
    
    # Add dummy verified claims
    mem.update_state("verified_claims", [
        {"claim": "Evidence works", "status": "verified"},
        {"claim": "Evidence questionable", "status": "uncertain"}
    ])
    
    stats = mem.get_summary_stats()
    assert stats["sub_questions_count"] == 2
    assert stats["total_sources"] == 1
    assert stats["total_chunks_stored"] == 10
    assert stats["summaries_count"] == 1
    assert stats["verified_claims_count"] == 1
    assert stats["unverified_claims_count"] == 1
    assert stats["status"] == "pending"
    print("✅ Test 10: summary_stats PASSED")

    # ----------------------------------------------------
    # Test 11: reset_state()
    # ----------------------------------------------------
    mem.reset_state()
    assert mem.get_field("sub_questions") == []
    assert mem.get_field("search_results") == []
    assert mem.get_field("final_report") == {}
    assert mem.get_field("topic") == "New AI Topic"
    assert mem.get_field("depth") == "expert"
    assert mem.get_field("language") == "spanish"
    assert mem.get_field("user_id") == "user1"
    print("✅ Test 11: reset_state PASSED")

    # ----------------------------------------------------
    # Test 12: WebSocketManager
    # ----------------------------------------------------
    manager = WebSocketManager()
    assert manager.connections == {}
    assert manager.is_connected("test_id") is False
    assert manager.get_connected_count() == 0
    print("✅ Test 12: WebSocketManager init PASSED")
    print("⚠️  WebSocket connection test: needs server")

    # ----------------------------------------------------
    # Test 13: Translator
    # ----------------------------------------------------
    assert get_language_prompt("english") != ""
    assert "हिन्दी" in get_language_prompt("hindi")
    assert "Español" in get_language_prompt("spanish")
    assert validate_language("english") == "english"
    assert validate_language("french") == "english"
    
    hindi_labels = get_report_labels("hindi")
    assert "कार्यकारी सारांश" in hindi_labels.values()
    
    all_langs = get_all_languages()
    assert len(all_langs) == 3
    print("✅ Test 13: Translator PASSED")

    # ----------------------------------------------------
    # Test 14: Full Pipeline Simulation
    # ----------------------------------------------------
    pipeline_mem = AgentMemory(
        report_id="rpt_sim1",
        topic="FastAPI WebSockets",
        depth="quick",
        language="english",
        user_id="user_pipeline"
    )
    
    # 1. Orchestrator started
    pipeline_mem.set_current_agent("orchestrator")
    pipeline_mem.update_state("status", "running")
    pipeline_mem.add_thinking_log("orchestrator", "Analyzing topics for socket server")
    pipeline_mem.update_state("sub_questions", ["How to configure fastapi websockets", "Is fastapi ws scaleable"])
    pipeline_mem.add_log("orchestrator", "done", "Generated 2 questions")
    
    # 2. Search Agent starts
    pipeline_mem.set_current_agent("search_agent")
    pipeline_mem.add_thinking_log("search_agent", "Submitting API searches to Tavily")
    pipeline_mem.update_state("search_results", [
        {
            "question": "How to configure fastapi websockets",
            "sources": [
                {"url": "https://fastapi.tiangolo.com/advanced/websockets/", "title": "FastAPI WebSockets Docs"}
            ]
        }
    ])
    pipeline_mem.add_log("search_agent", "done", "Searches finished")
    
    # 3. Complete pipeline
    pipeline_mem.set_status("done")
    
    # Assert checks on rehydrated state structure
    assert pipeline_mem.get_field("current_agent") == "search_agent"
    assert pipeline_mem.get_field("status") == "done"
    assert len(pipeline_mem.get_field("sub_questions")) == 2
    assert len(pipeline_mem.get_all_sources()) == 1
    
    sim_stats = pipeline_mem.get_summary_stats()
    print("--- Simulation Summary Stats ---")
    for k, v in sim_stats.items():
        print(f"  {k}: {v}")
    print("--------------------------------")
    
    print("✅ Test 14: Pipeline simulation PASSED")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 14 TESTS PASSED")
    print("Day 7 complete. Ready for Day 8.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()
