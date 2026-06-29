"""Standalone validation script for Day 13 (Writer Agent + FollowUp Agent).

This script tests:
1. build_context()
2. build_writer_prompt()
3. write_report() - main test
4. Report content validation
5. Key findings validation
6. Citations in report
7. Multi-language test - Hindi
8. build_followup_prompt()
9. generate_followup_questions()
10. followup_agent run()
11. parse_report_response()
12. Full pipeline D8-D13
13. Verify all sections have content
14. Cleanup
"""

from __future__ import annotations

import os
import sys
import time
import asyncio
import logging
import json
import re
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
from agents.writer_agent import (
    build_context,
    build_writer_prompt,
    write_report,
    parse_report_response
)
from agents.followup_agent import (
    build_followup_prompt,
    generate_followup_questions,
    run as fu_run
)
from tools.pinecone_tool import delete_report_chunks


def create_full_mock_state() -> AgentMemory:
    """Create a temporary test AgentMemory state initialized with mock claims and sources."""
    state = AgentMemory(
        report_id=f"test_writer_{int(time.time())}",
        topic="Benefits of regular exercise",
        depth="quick",
        language="english",
        user_id="test_user"
    )
    
    state.update_state("sub_questions", [
        "What are health benefits of exercise?",
        "How does exercise affect mental health?",
        "What does science say about exercise?"
    ])

    state.update_state("verified_claims", [
        {
            "claim": "30 minutes daily exercise reduces heart disease by 35%",
            "status": "verified",
            "supporting_sources": [
                "https://who.int/exercise",
                "https://cdc.gov/physical-activity"
            ],
            "evidence_count": 2,
            "avg_support_score": 0.91,
            "source_question": "What are health benefits?",
            "credibility_levels": ["government"]
        },
        {
            "claim": "Exercise improves cognitive function by 20% in adults",
            "status": "verified",
            "supporting_sources": [
                "https://harvard.edu/exercise",
                "https://nih.gov/cognitive"
            ],
            "evidence_count": 2,
            "avg_support_score": 0.88,
            "source_question": "How does exercise affect mental health?",
            "credibility_levels": ["academic"]
        },
        {
            "claim": "CDC recommends 150 minutes exercise per week",
            "status": "verified",
            "supporting_sources": [
                "https://cdc.gov/exercise-guidelines"
            ],
            "evidence_count": 1,
            "avg_support_score": 0.95,
            "source_question": "Science of exercise?",
            "credibility_levels": ["government"]
        },
        {
            "claim": "Exercise reduces depression symptoms by 40%",
            "status": "verified",
            "supporting_sources": [
                "https://bmj.com/exercise-depression",
                "https://pubmed.ncbi.nlm.nih.gov/exercise"
            ],
            "evidence_count": 2,
            "avg_support_score": 0.86,
            "source_question": "Mental health benefits?",
            "credibility_levels": ["academic"]
        },
        {
            "claim": "Exercise extends life expectancy by 3-7 years",
            "status": "uncertain",
            "supporting_sources": [
                "https://nejm.org/exercise-longevity"
            ],
            "evidence_count": 1,
            "avg_support_score": 0.72,
            "source_question": "Health benefits of exercise?",
            "credibility_levels": ["academic"]
        }
    ])

    state.update_state("summaries", [
        {
            "question": "What are health benefits of exercise?",
            "summary": (
                "Regular exercise provides numerous health benefits. Studies show "
                "30 minutes daily reduces heart disease by 35% [Source: who.int]. "
                "Exercise also improves cognitive function significantly [Source: harvard.edu]. "
                "The CDC recommends 150 minutes weekly [Source: cdc.gov]."
            ),
            "citations": [
                "https://who.int/exercise",
                "https://harvard.edu/exercise",
                "https://cdc.gov/physical-activity"
            ],
            "chunk_count": 5,
            "avg_relevance_score": 0.88,
            "word_count": 68,
            "language": "english"
        },
        {
            "question": "How does exercise affect mental health?",
            "summary": (
                "Exercise has profound mental health effects. Research shows 40% "
                "reduction in depression symptoms [Source: bmj.com]. Endorphin release "
                "improves mood immediately after exercise [Source: nih.gov]."
            ),
            "citations": [
                "https://bmj.com/exercise-depression",
                "https://nih.gov/endorphins"
            ],
            "chunk_count": 4,
            "avg_relevance_score": 0.85,
            "word_count": 45,
            "language": "english"
        }
    ])

    state.update_state("source_credibility", [
        {"url": "https://who.int/exercise", "rating": "government", "score": 90, "icon": "🏛️"},
        {"url": "https://harvard.edu/exercise", "rating": "academic", "score": 95, "icon": "🎓"},
        {"url": "https://cdc.gov/physical-activity", "rating": "government", "score": 90, "icon": "🏛️"},
        {"url": "https://bmj.com/exercise", "rating": "academic", "score": 95, "icon": "🎓"},
        {"url": "https://pubmed.ncbi.nlm.nih.gov/ex", "rating": "academic", "score": 95, "icon": "🎓"},
        {"url": "https://nih.gov/cognitive", "rating": "government", "score": 90, "icon": "🏛️"}
    ])

    state.update_state("confidence_score", 82)
    return state


# Shared test globals
shared_state = None
pipeline_state = None
pipeline_report_id = "full_d13_pipeline"


def test_1_build_context() -> None:
    """Test 1: Verify build_context compiles all necessary fields from the state."""
    state = create_full_mock_state()
    context = build_context(state)

    required_keys = [
        "topic", "language", "confidence", "sub_questions",
        "verified_facts", "uncertain_facts", "summaries",
        "verified_count", "uncertain_count", "source_details", "total_sources"
    ]
    for key in required_keys:
        assert key in context

    assert context["verified_count"] == 4
    assert context["uncertain_count"] == 1
    assert context["total_sources"] > 0
    assert context["verified_facts"] != ""

    print(f"  Verified: {context['verified_count']}")
    print(f"  Uncertain: {context['uncertain_count']}")
    print(f"  Sources: {context['total_sources']}")
    print("✅ Test 1: build_context PASSED")


def test_2_build_writer_prompt() -> None:
    """Test 2: Verify build_writer_prompt generates robust prompts with strict formatting rules."""
    state = create_full_mock_state()
    context = build_context(state)
    system, user = build_writer_prompt(context)

    assert system != ""
    assert user != ""
    assert "STRICT RULES" in system
    assert context["topic"] in user
    assert "JSON" in user
    assert "executive_summary" in user
    assert "key_findings" in user
    assert "detailed_analysis" in user
    assert "limitations" in user
    assert "conclusion" in user

    print(f"  System prompt: {len(system)} chars")
    print(f"  User prompt: {len(user)} chars")
    print("✅ Test 2: build_writer_prompt PASSED")


def test_3_write_report() -> None:
    """Test 3: Verify write_report successfully writes the report using OpenAI."""
    global shared_state
    shared_state = create_full_mock_state()
    report_id = shared_state.get_field("report_id")

    success = asyncio.run(
        write_report(shared_state, report_id)
    )

    assert success is True
    final_report = shared_state.get_field("final_report")
    assert final_report is not None
    assert isinstance(final_report, dict)

    print("\n📄 GENERATED REPORT STRUCTURE:")
    for key in final_report:
        value_preview = str(final_report[key])[:60]
        print(f"  {key}: {value_preview}...")

    print("✅ Test 3: write_report PASSED")


def test_4_report_content_validation() -> None:
    """Test 4: Validate structured sections, word count, and metadata values."""
    global shared_state
    assert shared_state is not None
    final_report = shared_state.get_field("final_report")

    assert final_report.get("title") and len(final_report["title"]) > 10
    assert final_report.get("executive_summary") and len(final_report["executive_summary"]) > 100
    assert isinstance(final_report.get("key_findings"), list)
    assert len(final_report["key_findings"]) >= 3
    assert final_report.get("detailed_analysis") and len(final_report["detailed_analysis"]) > 200
    assert final_report.get("limitations") and len(final_report["limitations"]) > 50
    assert final_report.get("conclusion") and len(final_report["conclusion"]) > 50
    assert final_report.get("word_count", 0) > 300
    assert final_report.get("confidence_score") == 82
    assert final_report.get("language") == "english"
    assert final_report.get("generated_at") != ""

    print("\n📊 REPORT STATS:")
    print(f"  Title: {final_report['title']}")
    print(f"  Words: {final_report['word_count']}")
    print(f"  Findings: {len(final_report['key_findings'])}")
    print(f"  Sources: {final_report['total_sources_used']}")
    print(f"  Confidence: {final_report['confidence_score']}%")
    print("✅ Test 4: Content validation PASSED")


def test_5_key_findings_validation() -> None:
    """Test 5: Verify fields structure and types of each finding."""
    global shared_state
    assert shared_state is not None
    final_report = shared_state.get_field("final_report")
    key_findings = final_report["key_findings"]

    for finding in key_findings:
        assert "point" in finding and len(finding["point"]) > 10
        assert "citation" in finding
        assert finding.get("status") in ["verified", "uncertain"]

    print("\n🔍 KEY FINDINGS:")
    for i, f in enumerate(key_findings, 1):
        print(f"  {i}. {f['point'][:65]}")
        print(f"     [{f['status']}] {f['citation'][:40]}")

    print("✅ Test 5: Key findings PASSED")


def test_6_citations_in_report() -> None:
    """Test 6: Verify inline citations presence inside executive summary and detailed analysis."""
    global shared_state
    assert shared_state is not None
    final_report = shared_state.get_field("final_report")
    executive = final_report.get("executive_summary", "")
    analysis = final_report.get("detailed_analysis", "")

    all_text = executive + analysis
    citation_count = len(re.findall(r'\[Source:', all_text))

    print(f"  Citations found: {citation_count}")
    assert citation_count >= 2
    print("✅ Test 6: Citations PASSED")


def test_7_multi_language_hindi() -> None:
    """Test 7: Verify Multi-Language translation writes correct headers and script for Hindi."""
    state_hindi = create_full_mock_state()
    state_hindi.update_state("language", "hindi")
    report_id = state_hindi.get_field("report_id")

    success = asyncio.run(
        write_report(state_hindi, report_id)
    )

    assert success is True
    report_hindi = state_hindi.get_field("final_report")
    assert report_hindi["language"] == "hindi"

    print("\n🇮🇳 HINDI REPORT PREVIEW:")
    print(report_hindi["executive_summary"][:200])
    print("✅ Test 7: Hindi language PASSED")


def test_8_build_followup_prompt() -> None:
    """Test 8: Verify build_followup_prompt compiles correct sub-questions and key findings."""
    topic = "Benefits of exercise"
    questions = ["Health benefits of exercise?", "Mental health and exercise?"]
    mock_report = {
        "title": "Exercise Research Report",
        "key_findings": [
            {"point": "35% heart disease reduction"},
            {"point": "20% cognitive improvement"}
        ]
    }

    system, user = build_followup_prompt(topic, questions, mock_report)
    assert system != ""
    assert user != ""
    assert topic in user
    assert "5" in user
    assert "NOT covered" in user

    print("✅ Test 8: Followup prompt PASSED")


def test_9_generate_followup_questions() -> None:
    """Test 9: Verify generate_followup_questions produces valid strings ending with question marks."""
    state = create_full_mock_state()
    
    # Generate report first
    asyncio.run(write_report(state, state.get_field("report_id")))

    questions = asyncio.run(
        generate_followup_questions(state, state.get_field("report_id"))
    )

    assert isinstance(questions, list)
    assert len(questions) == 5
    for q in questions:
        assert isinstance(q, str)
        assert q.endswith("?")
        assert len(q) > 15

    print("\n🔮 FOLLOW-UP QUESTIONS:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")

    print("✅ Test 9: Followup questions PASSED")


def test_10_followup_agent_run() -> None:
    """Test 10: Verify FollowUp Agent run updates final state correctly."""
    state = create_full_mock_state()
    asyncio.run(write_report(state, state.get_field("report_id")))

    success = asyncio.run(
        fu_run(state, state.get_field("report_id"))
    )

    assert success is True
    followup = state.get_field("followup_questions", [])
    assert len(followup) == 5

    print(f"  Follow-up questions: {len(followup)}")
    print("✅ Test 10: followup run() PASSED")


def test_11_parse_report_response() -> None:
    """Test 11: Validate parse_report_response safety hooks for correct JSON formats and invalid text."""
    valid_json = json.dumps({
        "title": "Test Report",
        "executive_summary": "This is a test " * 20,
        "key_findings": [
            {"point": "Finding 1", "citation": "https://test.com", "status": "verified"}
        ],
        "detailed_analysis": "Analysis " * 60,
        "limitations": "Some limitations exist " * 10,
        "conclusion": "In conclusion " * 10
    })

    mock_context = {
        "language": "english",
        "confidence": 75,
        "sub_questions": [],
        "total_sources": 3,
        "source_details": []
    }

    result = parse_report_response(valid_json, mock_context)
    assert result is not None
    assert result["title"] == "Test Report"
    assert result["word_count"] > 0
    assert result["language"] == "english"

    # Test parser robustness with completely invalid JSON content
    result_invalid = parse_report_response("completely invalid text !!!", mock_context)
    assert result_invalid is None

    print("✅ Test 11: parse_response PASSED")


def test_12_full_pipeline() -> None:
    """Test 12: Verify execution of full Day 8 to 13 integrated orchestrator pipeline."""
    global pipeline_report_id, pipeline_state
    from agents.orchestrator import start_research

    state = asyncio.run(
        start_research(
            report_id=pipeline_report_id,
            topic="Impact of social media on teenagers",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )

    pipeline_state = state
    final_report = state.get_field("final_report")
    followup = state.get_field("followup_questions")
    status = state.get_field("status")
    confidence = state.get_field("confidence_score")

    assert final_report is not None
    assert final_report.get("title") != ""
    assert len(final_report.get("key_findings", [])) >= 3
    assert followup is not None
    assert len(followup) == 5
    assert status == "done"
    assert 0 <= confidence <= 100

    print("\n🔬 COMPLETE D13 PIPELINE:")
    print(f"  Title: {final_report.get('title')}")
    print(f"  Words: {final_report.get('word_count')}")
    print(f"  Confidence: {confidence}%")
    print(f"  Followup questions: {len(followup)}")
    print(f"  Status: {status}")
    print("✅ Test 12: Full pipeline PASSED")


def test_13_verify_sections_content() -> None:
    """Test 13: Verify all 6 report sections have non-empty valid content from Test 12."""
    global pipeline_state
    assert pipeline_state is not None, "Pipeline state is None. Did Test 12 fail?"
    final_report = pipeline_state.get_field("final_report")

    sections = [
        "title", "executive_summary",
        "key_findings", "detailed_analysis",
        "limitations", "conclusion"
    ]
    for section in sections:
        value = final_report.get(section)
        assert value is not None
        assert value != ""
        if isinstance(value, list):
            assert len(value) > 0
        else:
            assert len(str(value)) > 20
        print(f"  ✅ {section}: OK")

    print("✅ Test 13: All sections PASSED")


def test_14_cleanup() -> None:
    """Test 14: Delete Pinecone vectors for clean up."""
    global pipeline_report_id
    success = delete_report_chunks(pipeline_report_id)
    assert success is True
    print("✅ Test 14: Cleanup PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 13 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    test_1_build_context()
    test_2_build_writer_prompt()
    test_3_write_report()
    test_4_report_content_validation()
    test_5_key_findings_validation()
    test_6_citations_in_report()
    test_7_multi_language_hindi()
    test_8_build_followup_prompt()
    test_9_generate_followup_questions()
    test_10_followup_agent_run()
    test_11_parse_report_response()
    test_12_full_pipeline()
    test_13_verify_sections_content()
    test_14_cleanup()

    # Get final values for prints
    final_words = shared_state.get_field("final_report").get("word_count") if shared_state else 0
    final_conf = shared_state.get_field("confidence_score") if shared_state else 0

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 14 TESTS PASSED")
    print("Writer + FollowUp Agents complete!")
    print("Full pipeline D8-D13 working!")
    print(f"Report: {final_words} words")
    print(f"Confidence: {final_conf}%")
    print("Ready for Day 14: PDF Export")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
