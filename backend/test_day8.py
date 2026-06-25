"""Standalone validation script for Day 8 (Orchestrator Agent).

This script verifies all requirements of the Orchestrator agent including:
- depth to question count mapping
- OpenAI prompt builder
- response parser strategies (JSON, regex, list cleaning)
- sub-question generation across depths and topic variety
- retry and fallback mechanisms on API failure
- pipeline execution and the start_research API entry point
"""

from __future__ import annotations

import os
import sys
import time
import asyncio
import logging
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

# Configure logging
logging.basicConfig(level=logging.WARNING)

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from memory.agent_memory import AgentMemory
from agents.orchestrator import (
    get_question_count,
    build_orchestrator_prompt,
    parse_questions_from_response,
    generate_sub_questions,
    run_pipeline,
    start_research
)
import agents.orchestrator as orch


def create_test_state(topic: str, depth: str = "deep") -> AgentMemory:
    """Create a temporary test AgentMemory state."""
    return AgentMemory(
        report_id=f"test_{depth}_{int(time.time())}",
        topic=topic,
        depth=depth,
        language="english",
        user_id="test_user"
    )


def test_1_question_count() -> None:
    """Test 1: Verify get_question_count mappings."""
    assert get_question_count("quick") == 3
    assert get_question_count("deep") == 4
    assert get_question_count("expert") == 6
    # Fallback to default (4) for unknown depths
    assert get_question_count("unknown_depth_value") == 4
    print("✅ Test 1: Question count PASSED")


def test_2_prompt_builder() -> None:
    """Test 2: Verify prompt content structure."""
    topic = "AI in Healthcare"
    question_count = 4
    language = "english"
    
    sys_p, usr_p = build_orchestrator_prompt(topic, question_count, language)
    
    assert isinstance(sys_p, str) and len(sys_p) > 0
    assert isinstance(usr_p, str) and len(usr_p) > 0
    assert topic in usr_p
    assert str(question_count) in usr_p
    assert "JSON" in usr_p
    print("✅ Test 2: Prompt builder PASSED")


def test_3_parser() -> None:
    """Test 3: Verify parsing strategies."""
    # Test 3.1: Valid JSON array
    input_1 = '["Q1?", "Q2?", "Q3?", "Q4?"]'
    res_1 = parse_questions_from_response(input_1, 4)
    assert len(res_1) == 4
    assert res_1 == ["Q1?", "Q2?", "Q3?", "Q4?"]

    # Test 3.2: JSON with extra text
    input_2 = 'Here are the questions:\n["Q1?", "Q2?"]'
    res_2 = parse_questions_from_response(input_2, 2)
    assert len(res_2) == 2
    assert res_2 == ["Q1?", "Q2?"]

    # Test 3.3: Numbered list format
    input_3 = "1. Q1?\n2. Q2?\n3. Q3?"
    res_3 = parse_questions_from_response(input_3, 3)
    assert len(res_3) == 3
    assert res_3 == ["Q1?", "Q2?", "Q3?"]

    # Test 3.4: Empty / invalid input
    input_4 = "I cannot generate questions"
    res_4 = parse_questions_from_response(input_4, 4)
    assert res_4 == []
    print("✅ Test 3: Parser PASSED")


def test_4_generate_deep() -> None:
    """Test 4: Verify generate_sub_questions with DEEP depth."""
    state = create_test_state("Impact of AI on Healthcare", "deep")
    questions = asyncio.run(
        generate_sub_questions(state, state.get_field("report_id"))
    )
    
    assert len(questions) == 4
    for idx, q in enumerate(questions, 1):
        assert isinstance(q, str)
        assert q.endswith("?")
        assert len(q) > 15
        print(f"  {idx}. {q}")
    print("✅ Test 4: Deep research PASSED")


def test_5_generate_quick() -> None:
    """Test 5: Verify generate_sub_questions with QUICK depth."""
    state = create_test_state("Climate change solutions", "quick")
    questions = asyncio.run(
        generate_sub_questions(state, state.get_field("report_id"))
    )
    
    assert len(questions) == 3
    print("✅ Test 5: Quick research PASSED")


def test_6_generate_expert() -> None:
    """Test 6: Verify generate_sub_questions with EXPERT depth."""
    state = create_test_state("Future of electric vehicles", "expert")
    questions = asyncio.run(
        generate_sub_questions(state, state.get_field("report_id"))
    )
    
    assert len(questions) == 6
    print("✅ Test 6: Expert research PASSED")


def test_7_topic_variety() -> None:
    """Test 7: Verify generation against various topics."""
    topics = [
        "Blockchain in finance",
        "Space exploration 2025",
        "Mental health and social media",
        "Quantum computing applications",
        "Sustainable agriculture"
    ]
    
    for topic in topics:
        state = create_test_state(topic, "deep")
        questions = asyncio.run(
            generate_sub_questions(state, state.get_field("report_id"))
        )
        assert len(questions) == 4
        
        # Verify questions mention key terms of the topic
        key_words = [
            w.lower() for w in topic.replace("and", "").replace("in", "").split()
            if len(w) > 2
        ]
        keyword_matched = False
        for kw in key_words:
            for q in questions:
                if kw in q.lower():
                    keyword_matched = True
                    break
        assert keyword_matched, f"No keyword from '{topic}' found in: {questions}"
        
        print(f"Topic: {topic}")
        for q in questions:
            print(f"  - {q}")
            
    print("✅ Test 7: Topic variety PASSED")


def test_8_state_updates() -> None:
    """Test 8: Verify state updates after generation."""
    state = create_test_state("AI ethics")
    asyncio.run(
        generate_sub_questions(state, "test_id")
    )
    
    assert state.get_field("sub_questions") != []
    assert len(state.get_field("sub_questions")) == 4
    assert len(state.get_field("logs")) > 0
    assert len(state.get_field("thinking_logs")) > 0
    print("✅ Test 8: State update PASSED")


def test_9_empty_topic() -> None:
    """Test 9: Verify graceful handling of empty topic."""
    state = create_test_state("")
    # Empty topic shouldn't crash, should return fallbacks or valid empty structure
    questions = asyncio.run(
        generate_sub_questions(state, "test_id")
    )
    assert isinstance(questions, list)
    print("✅ Test 9: Empty topic handled PASSED")


def test_10_fallback() -> None:
    """Test 10: Verify fallback questions generation on API failures."""
    # Part 1: parsing failure returns empty list
    parsed = parse_questions_from_response("completely invalid response ###", 4)
    assert parsed == []

    # Part 2: Mock API failure and verify fallback questions
    old_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "invalid_key_to_force_failure"
    
    # Save active orchestrator client and invalidate
    original_client = orch._client
    orch._client = None
    
    try:
        topic = "Meditation benefits"
        state = create_test_state(topic, "deep")
        questions = asyncio.run(
            generate_sub_questions(state, "test_id")
        )
        
        assert len(questions) == 4
        # Fallbacks should contain the topic
        for q in questions:
            assert topic.lower() in q.lower()
    finally:
        # Restore environment and client singleton
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        orch._client = original_client

    print("✅ Test 10: Fallback PASSED")


def test_11_pipeline_runner() -> None:
    """Test 11: Verify run_pipeline works today."""
    state = create_test_state("Renewable energy trends")
    asyncio.run(
        run_pipeline(state, state.get_field("report_id"))
    )
    
    assert state.get_field("status") == "done"
    assert state.get_field("sub_questions") != []
    assert state.get_field("current_agent") is not None
    print("✅ Test 11: Pipeline runner PASSED")


def test_12_start_research_entry() -> None:
    """Test 12: Verify start_research endpoint coordinator."""
    final_state = asyncio.run(
        start_research(
            report_id="test_start_123",
            topic="Artificial General Intelligence",
            depth="deep",
            language="english",
            user_id="test_user_456"
        )
    )
    
    assert isinstance(final_state, AgentMemory)
    assert final_state.get_field("status") == "done"
    assert len(final_state.get_field("sub_questions")) == 4
    
    print("\nQuestions Generated:")
    for idx, q in enumerate(final_state.get_field("sub_questions"), 1):
        print(f"  {idx}. {q}")
        
    # Print summary stats
    stats = final_state.get_summary_stats()
    print(f"\nFinal State Summary Stats: {stats}")
    print("✅ Test 12: start_research PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 8 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    test_1_question_count()
    test_2_prompt_builder()
    test_3_parser()
    test_4_generate_deep()
    test_5_generate_quick()
    test_6_generate_expert()
    test_7_topic_variety()
    test_8_state_updates()
    test_9_empty_topic()
    test_10_fallback()
    test_11_pipeline_runner()
    test_12_start_research_entry()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 12 TESTS PASSED")
    print("Orchestrator ready for Day 9")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
