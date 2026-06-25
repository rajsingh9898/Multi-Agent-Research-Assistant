"""Standalone validation script for Day 9 (Search Agent).

This script verifies all 10 test requirements of the search agent including:
- validation of sub-questions
- single question search schema structure
- multi-question search runs
- source content and credibility quality metrics
- AgentMemory state updates and handoffs
- search statistics generation
- integration with Day 8 orchestrator in a full pipeline run
- performance benchmark limits
"""

from __future__ import annotations

import os
import sys
import time
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup sys.path to allow imports from both root and backend folders
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(level=logging.WARNING)

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from memory.agent_memory import AgentMemory
from agents.search_agent import (
    validate_sub_questions,
    search_single_question,
    collect_all_source_credibility,
    run,
    get_search_stats
)


def create_test_state_with_questions(topic: str, questions: list[str], depth: str = "deep") -> AgentMemory:
    """Helper function to create a test AgentMemory initialized with sub-questions."""
    state = AgentMemory(
        report_id=f"test_search_{int(time.time())}_{topic[:5].strip()}",
        topic=topic,
        depth=depth,
        language="english",
        user_id="test_user"
    )
    state.update_state("sub_questions", questions)
    return state


def test_1_validation() -> None:
    """Test 1: Verify validate_sub_questions filters inputs correctly."""
    # State with valid questions
    state_ok = create_test_state_with_questions("T1", ["What is artificial intelligence?", "Why does machine learning work?"])
    assert len(validate_sub_questions(state_ok)) == 2

    # State with empty questions
    state_empty = create_test_state_with_questions("T1", [])
    assert validate_sub_questions(state_empty) == []

    # State with short or empty strings
    state_dirty = create_test_state_with_questions("T1", ["valid question length check", "", "short", "   ", "another valid question string"])
    cleaned = validate_sub_questions(state_dirty)
    assert len(cleaned) == 2
    assert "short" not in cleaned
    assert "" not in cleaned
    print("✅ Test 1: Validation PASSED")


def test_2_single_search() -> None:
    """Test 2: Verify search_single_question schema structure."""
    question = "What is artificial intelligence?"
    report_id = "test_single_001"
    state = create_test_state_with_questions("AI Basics", [question])
    
    result = asyncio.run(
        search_single_question(
            question=question,
            question_index=1,
            total_questions=1,
            report_id=report_id,
            state=state
        )
    )
    
    assert result is not None
    assert "question" in result
    assert result["question"] == question
    assert "sources" in result
    assert isinstance(result["sources"], list)
    assert "source_count" in result
    assert isinstance(result["source_count"], int)
    assert "avg_credibility_score" in result
    assert isinstance(result["avg_credibility_score"], int)

    sources = result["sources"]
    print(f"  Found {len(sources)} sources for: '{question}'")
    for idx, src in enumerate(sources, 1):
        assert "title" in src
        assert "url" in src
        assert "content" in src
        assert "credibility" in src
        assert "credibility_icon" in src
        assert "word_count" in src
        print(f"    Source {idx}: {src['title'][:40]} | [{src['credibility']}]")
        
    print("✅ Test 2: Single search PASSED")


# Global placeholder to pass data between tests
test_3_state = None


def test_3_run_multi() -> None:
    """Test 3: Run search agent against 3 questions."""
    global test_3_state
    questions = [
        "What are the latest AI research tools?",
        "How is machine learning used in healthcare?",
        "What are Python frameworks for AI development?"
    ]
    test_3_state = create_test_state_with_questions("AI Tools and Applications", questions)
    
    result = asyncio.run(
        run(test_3_state, test_3_state.get_field("report_id"))
    )
    
    assert result is True
    search_results = test_3_state.get_field("search_results")
    assert len(search_results) == 3
    
    total = sum(r.get("source_count", 0) for r in search_results)
    assert total >= 6, f"Expected at least 6 sources, found {total}"
    
    print(f"  Total sources found: {total}")
    for idx, r in enumerate(search_results, 1):
        print(f"    Q{idx} ({r['question'][:30]}...): {r['source_count']} sources")
        
    print("✅ Test 3: 3 questions PASSED")


def test_4_content_quality() -> None:
    """Test 4: Verify search source content quality."""
    global test_3_state
    assert test_3_state is not None
    search_results = test_3_state.get_field("search_results")
    
    for r in search_results:
        for src in r.get("sources", []):
            assert len(src.get("content", "")) > 100
            assert src.get("url", "").startswith("https://") or src.get("url", "").startswith("http://")
            assert src.get("title") != ""
            assert src.get("credibility", "").lower() in ["academic", "news", "blog", "government", "unknown"]
            
    print("✅ Test 4: Content quality PASSED")


def test_5_credibility_distribution() -> None:
    """Test 5: Verify credibility classification breakdown."""
    global test_3_state
    assert test_3_state is not None
    search_results = test_3_state.get_field("search_results")
    
    dist = {"academic": 0, "news": 0, "blog": 0, "unknown": 0}
    for r in search_results:
        for src in r.get("sources", []):
            rating = src.get("credibility")
            assert rating is not None
            rating_lower = rating.lower().strip()
            if rating_lower == "government":
                rating_lower = "academic"
            if rating_lower in dist:
                dist[rating_lower] += 1
            else:
                dist["unknown"] += 1
                
    print(f"  Distribution: Academic: {dist['academic']} | News: {dist['news']} | Blog: {dist['blog']} | Unknown: {dist['unknown']}")
    print("✅ Test 5: Credibility PASSED")


def test_6_state_updated() -> None:
    """Test 6: Verify memory state modifications after complete execution."""
    state = create_test_state_with_questions(
        "Space exploration",
        ["What is NASA working on in 2025?", "How do rockets reach orbit?"]
    )
    
    result = asyncio.run(
        run(state, state.get_field("report_id"))
    )
    assert result is True
    assert state.get_field("search_results") != []
    assert state.get_field("source_credibility") != []
    assert state.get_field("current_agent") == "summary_agent"
    assert len(state.get_field("logs")) > 0
    assert len(state.get_field("thinking_logs")) > 0
    print("✅ Test 6: State update PASSED")


def test_7_get_stats() -> None:
    """Test 7: Verify search stats output keys."""
    # Create and run a minimal state to get fresh stats
    state = create_test_state_with_questions(
        "Space exploration",
        ["What is NASA working on in 2025?", "How do rockets reach orbit?"]
    )
    asyncio.run(run(state, state.get_field("report_id")))
    
    stats = get_search_stats(state)
    required_keys = [
        "total_questions_searched",
        "total_sources_found",
        "avg_sources_per_question",
        "avg_credibility_score",
        "credibility_breakdown",
        "top_3_sources",
        "sources_per_question"
    ]
    for key in required_keys:
        assert key in stats
        
    print(f"  Full Stats: {stats}")
    print("✅ Test 7: Stats PASSED")


def test_8_empty_sub_questions() -> None:
    """Test 8: Verify empty questions error handler."""
    state = create_test_state_with_questions("test topic", [])
    result = asyncio.run(
        run(state, state.get_field("report_id"))
    )
    assert result is False
    assert state.get_field("status") == "failed"
    print("✅ Test 8: Empty questions PASSED")


def test_9_full_pipeline() -> None:
    """Test 9: Run combined Day 8 + Day 9 pipeline."""
    from agents.orchestrator import start_research

    final_state = asyncio.run(
        start_research(
            report_id="pipeline_test_d9",
            topic="Benefits of renewable energy",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )

    sub_questions = final_state.get_field("sub_questions")
    search_results = final_state.get_field("search_results")
    
    assert len(sub_questions) == 3
    assert len(search_results) == 3
    
    total_sources = sum(r["source_count"] for r in search_results)
    assert total_sources >= 6

    print("\n🔬 PIPELINE TEST RESULTS:")
    print("  Topic: Benefits of renewable energy")
    print(f"  Sub-questions: {len(sub_questions)}")
    for idx, r in enumerate(search_results, 1):
        print(f"    Q{idx}: {r['question'][:40]}... (Sources: {r['source_count']})")
    print(f"  Total sources: {total_sources}")
    print("✅ Test 9: Full pipeline PASSED")


def test_10_performance() -> None:
    """Test 10: Verify performance execution timer."""
    start_time = time.time()
    state = create_test_state_with_questions(
        "Quantum computing",
        ["What is quantum computing?", "How does quantum entanglement work?"]
    )
    asyncio.run(
        run(state, state.get_field("report_id"))
    )
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"  Search time: {elapsed:.1f} seconds")
    assert elapsed < 30.0, f"Expected execution < 30s, got {elapsed:.1f}s"
    print("✅ Test 10: Performance PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 9 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    test_1_validation()
    test_2_single_search()
    test_3_run_multi()
    test_4_content_quality()
    test_5_credibility_distribution()
    test_6_state_updated()
    test_7_get_stats()
    test_8_empty_sub_questions()
    # Test 9 will run once orchestrator is updated, but let's run it as well!
    test_9_full_pipeline()
    test_10_performance()
    
    # Generate final stats mapping from last test run
    # Let's get final stats from test_3_state
    final_stats = get_search_stats(test_3_state) if test_3_state else {}
    total_srcs = final_stats.get("total_sources_found", 0)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 10 TESTS PASSED")
    print(f"Total sources in last test: {total_srcs}")
    print("Search Agent ready for Day 10")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
