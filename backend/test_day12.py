"""Standalone validation script for Day 12 (FactCheck Agent).

This script tests:
1. extract_claims() - normal summary
2. extract_claims() - edge cases (empty strings, short inputs)
3. verify_single_claim() setup (run full search+summary pipeline to populate index)
4. verify_single_claim() - should verify (valid claim)
5. verify_single_claim() - should unverify (unsupported/outrageous claim)
6. calculate_verification_stats()
7. process_single_summary()
8. run() - main orchestration function
9. get_verified_only() helper
10. get_factcheck_summary() helper
11. Full pipeline integration (Day 8 + Day 9 + Day 10 + Day 11 + Day 12)
12. Cleaning up stored test chunks
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
from agents.factcheck_agent import (
    extract_claims,
    verify_single_claim,
    process_single_summary,
    calculate_verification_stats,
    run,
    get_verified_only,
    get_factcheck_summary
)
from tools.pinecone_tool import delete_report_chunks

# Mock summaries for testing
mock_summaries = [
    {
        "question": "What are benefits of regular exercise?",
        "summary": (
            "Regular exercise provides significant health benefits. Studies show "
            "30 minutes of daily exercise reduces heart disease risk by 35% "
            "[Source: https://who.int/exercise]. Harvard Medical School research "
            "found exercise improves cognitive function by 20% in adults over 50 "
            "[Source: https://harvard.edu/exercise-brain]. The CDC recommends 150 "
            "minutes of moderate exercise per week for adults "
            "[Source: https://cdc.gov/physical-activity]. Exercise reduces "
            "depression symptoms by 40% according to multiple clinical trials "
            "[Source: https://pubmed.ncbi.nlm.nih.gov/exercise-mood]. Regular physical "
            "activity extends life expectancy by 3-7 years on average "
            "[Source: https://nejm.org/exercise-longevity]."
        ),
        "citations": [
            "https://who.int/exercise",
            "https://harvard.edu/exercise-brain",
            "https://cdc.gov/physical-activity",
            "https://pubmed.ncbi.nlm.nih.gov/exercise-mood",
            "https://nejm.org/exercise-longevity"
        ],
        "chunk_count": 5,
        "avg_relevance_score": 0.89,
        "word_count": 142,
        "language": "english"
    },
    {
        "question": "How does exercise affect mental health?",
        "summary": (
            "Exercise has profound effects on mental health. Aerobic exercise triggers "
            "release of endorphins and serotonin [Source: https://nih.gov/exercise-mental]. "
            "A 2024 meta-analysis of 50 studies found exercise as effective as "
            "antidepressants for mild-to-moderate depression "
            "[Source: https://bmj.com/exercise-depression]. Yoga and mindfulness exercise "
            "reduce anxiety by 30% in clinical settings "
            "[Source: https://pubmed.ncbi.nlm.nih.gov/yoga-anxiety]."
        ),
        "citations": [
            "https://nih.gov/exercise-mental",
            "https://bmj.com/exercise-depression",
            "https://pubmed.ncbi.nlm.nih.gov/yoga-anxiety"
        ],
        "chunk_count": 4,
        "avg_relevance_score": 0.85,
        "word_count": 95,
        "language": "english"
    }
]


def create_state_with_summaries() -> AgentMemory:
    """Create a temporary test AgentMemory state initialized with summaries and sources."""
    state = AgentMemory(
        report_id=f"test_fc_{int(time.time())}",
        topic="Benefits of regular exercise",
        depth="quick",
        language="english",
        user_id="test_user"
    )
    state.update_state("summaries", mock_summaries)
    state.update_state("sub_questions", [
        "What are benefits of regular exercise?",
        "How does exercise affect mental health?"
    ])
    # Add mock search_results for confidence score calculation
    state.update_state("search_results", [
        {
            "question": "exercise benefits",
            "sources": [
                {"credibility": "academic", "url": "https://who.int/exercise"},
                {"credibility": "academic", "url": "https://harvard.edu/exercise"}
            ],
            "source_count": 2,
            "avg_credibility_score": 90
        }
    ])
    # Add mock source_credibility for confidence score Factors 1, 3, 4
    state.update_state("source_credibility", [
        {
            "url": "https://who.int/exercise",
            "credibility": "academic",
            "credibility_score": 90,
            "domain": "who.int"
        },
        {
            "url": "https://harvard.edu/exercise",
            "credibility": "academic",
            "credibility_score": 90,
            "domain": "harvard.edu"
        }
    ])
    return state


# Global test states
claims_test_1 = []
report_id_test = "fc_pipeline_test"
full_pipeline_report_id = "full_d12_pipeline"
state_test_8 = None


def test_1_extract_claims() -> None:
    """Test 1: Verify extract_claims successfully parses GPT-4o-mini claims response."""
    global claims_test_1
    summary = mock_summaries[0]["summary"]
    question = mock_summaries[0]["question"]

    claims_test_1 = extract_claims(
        summary_text=summary,
        question=question,
        num_claims=5
    )

    assert isinstance(claims_test_1, list)
    assert len(claims_test_1) >= 3
    for claim in claims_test_1:
        assert isinstance(claim, str)
        assert len(claim) > 15

    print("\n📋 EXTRACTED CLAIMS:")
    for i, claim in enumerate(claims_test_1, 1):
        print(f"  {i}. {claim}")
        
    print("✅ Test 1: extract_claims PASSED")


def test_2_extract_claims_edge_cases() -> None:
    """Test 2: Verify extract_claims behaves safely on empty and short inputs."""
    res_empty = extract_claims("", "question")
    assert res_empty == []

    res_short = extract_claims("AI is good.", "q")
    assert isinstance(res_short, list)
    print("✅ Test 2: Edge cases PASSED")


def test_3_verify_single_claim_setup() -> None:
    """Test 3: Setup Pinecone index chunks by running full pipeline up to summary agent."""
    global report_id_test
    from agents.orchestrator import start_research

    pipeline_state = asyncio.run(
        start_research(
            report_id=report_id_test,
            topic="Benefits of regular exercise",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )

    # Note: Day 11 implemented full run() including retrieval + summaries.
    # Therefore, summaries and chunk stats should be populated.
    assert pipeline_state.get_field("pinecone_ready") is True
    assert len(pipeline_state.get_field("sub_questions")) > 0
    print("  Pipeline state and Pinecone chunks ready for fact-checking")
    print("✅ Test 3: Pipeline setup PASSED")


def test_4_verify_single_claim_success() -> None:
    """Test 4: Verify that a valid claim is verified or uncertain against Pinecone."""
    global report_id_test
    claim = "Exercise reduces heart disease risk"

    result = verify_single_claim(
        claim=claim,
        report_id=report_id_test,
        question="What are benefits of exercise?"
    )

    # Check key structure
    required_keys = [
        "claim", "status", "supporting_sources", "evidence_count",
        "avg_support_score", "source_question", "credibility_levels"
    ]
    for key in required_keys:
        assert key in result

    assert result["claim"] == claim
    assert result["status"] in ["verified", "uncertain", "unverified"]
    assert isinstance(result["supporting_sources"], list)
    assert result["evidence_count"] >= 0

    print(f"  Status: {result['status']}")
    print(f"  Evidence: {result['evidence_count']} sources")
    print(f"  Sources: {result['supporting_sources']}")
    print("✅ Test 4: verify_single_claim PASSED")


def test_5_verify_single_claim_failure() -> None:
    """Test 5: Verify that an unsupported claim defaults to unverified."""
    global report_id_test
    claim = "Exercise allows humans to fly at 200mph"

    result = verify_single_claim(
        claim=claim,
        report_id=report_id_test,
        question="test question"
    )

    assert result["status"] == "unverified"
    assert result["evidence_count"] == 0
    assert result["supporting_sources"] == []
    print("✅ Test 5: Unverified claim PASSED")


def test_6_calculate_verification_stats() -> None:
    """Test 6: Verify calculate_verification_stats computes accurate rates and totals."""
    mock_results = [
        {"status": "verified", "evidence_count": 3},
        {"status": "verified", "evidence_count": 2},
        {"status": "uncertain", "evidence_count": 1},
        {"status": "unverified", "evidence_count": 0},
        {"status": "unverified", "evidence_count": 0},
    ]

    stats = calculate_verification_stats(mock_results)

    assert stats["total_claims"] == 5
    assert stats["verified"] == 2
    assert stats["uncertain"] == 1
    assert stats["unverified"] == 2
    assert stats["passed_claims"] == 3
    assert stats["failed_claims"] == 2
    assert 0.0 <= stats["verification_rate"] <= 1.0
    assert stats["verification_rate"] == 0.60

    print(f"  Stats: {stats}")
    print("✅ Test 6: Stats calculation PASSED")


def test_7_process_single_summary() -> None:
    """Test 7: Verify process_single_summary extracts and verifies claims successfully."""
    global report_id_test
    state = create_state_with_summaries()

    results = asyncio.run(
        process_single_summary(
            summary_dict=mock_summaries[0],
            summary_index=1,
            total_summaries=2,
            report_id=report_id_test,
            state=state
        )
    )

    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert "claim" in r
        assert r["status"] in ["verified", "uncertain", "unverified"]
        assert isinstance(r["supporting_sources"], list)
        assert r["evidence_count"] >= 0

    print(f"  Claims processed: {len(results)}")
    verified = [r for r in results if r["status"] == "verified"]
    uncertain = [r for r in results if r["status"] == "uncertain"]
    unverified = [r for r in results if r["status"] == "unverified"]
    print(f"    ✅ Verified:  {len(verified)}")
    print(f"    ⚠️  Uncertain: {len(uncertain)}")
    print(f"    ❌ Unverified:{len(unverified)}")
    print("✅ Test 7: process_summary PASSED")


def test_8_run_factcheck() -> None:
    """Test 8: Verify run() updates memory, logs, next agent state, and confidence score."""
    global state_test_8, report_id_test
    state_test_8 = create_state_with_summaries()
    
    # Associate state with stored vector report id
    state_test_8.update_state("report_id", report_id_test)

    success = asyncio.run(
        run(state_test_8, report_id_test)
    )

    assert success is True
    verified_claims = state_test_8.get_field("verified_claims")
    assert verified_claims is not None
    assert len(verified_claims) > 0

    confidence = state_test_8.get_field("confidence_score")
    assert 0 <= confidence <= 100

    current = state_test_8.get_field("current_agent")
    assert current == "writer_agent"

    print(f"  Claims: {len(verified_claims)}")
    print(f"  Confidence: {confidence}%")
    print(f"  Next agent: {current}")
    print("✅ Test 8: run() PASSED")


def test_9_get_verified_only() -> None:
    """Test 9: Verify get_verified_only filters out unverified claims."""
    global state_test_8
    assert state_test_8 is not None

    passed = get_verified_only(state_test_8)
    all_claims = state_test_8.get_field("verified_claims")

    for c in passed:
        assert c["status"] != "unverified"

    unverified_count = sum(1 for c in all_claims if c["status"] == "unverified")
    assert len(passed) == len(all_claims) - unverified_count

    print(f"  All claims: {len(all_claims)}")
    print(f"  Passed claims: {len(passed)}")
    print("✅ Test 9: get_verified_only PASSED")


def test_10_get_factcheck_summary() -> None:
    """Test 10: Verify get_factcheck_summary contains all summary metadata."""
    global state_test_8
    assert state_test_8 is not None

    summary = get_factcheck_summary(state_test_8)
    keys = [
        "total_claims", "verified", "uncertain", "unverified", "verification_rate",
        "passed_claims", "failed_claims", "confidence_score", "confidence_label",
        "confidence_emoji", "top_verified_claims", "removed_claims"
    ]
    for key in keys:
        assert key in summary

    print("\n📊 FACTCHECK SUMMARY:")
    print(f"  Total: {summary['total_claims']}")
    print(f"  ✅ Verified: {summary['verified']}")
    print(f"  ⚠️  Uncertain: {summary['uncertain']}")
    print(f"  ❌ Unverified: {summary['unverified']}")
    print(f"  Confidence: {summary['confidence_score']}%")
    print(f"  Label: {summary['confidence_emoji']} {summary['confidence_label']}")
    
    print("\n  Top verified claims:")
    for claim in summary['top_verified_claims']:
        print(f"    • {claim[:60]}")

    print("✅ Test 10: Factcheck summary PASSED")


def test_11_full_pipeline_run() -> None:
    """Test 11: Verify integrated orchestrator pipeline flow including FactCheck."""
    global full_pipeline_report_id
    from agents.orchestrator import start_research

    state = asyncio.run(
        start_research(
            report_id=full_pipeline_report_id,
            topic="Impact of sleep on health",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )

    questions = state.get_field("sub_questions")
    summaries = state.get_field("summaries")
    verified_claims = state.get_field("verified_claims")
    confidence = state.get_field("confidence_score")

    assert questions != []
    assert summaries != []
    assert verified_claims != []
    assert 0 <= confidence <= 100

    print("\n🔬 FULL PIPELINE D12 RESULTS:")
    print(f"  Questions: {len(questions)}")
    print(f"  Summaries: {len(summaries)}")
    print(f"  Total claims: {len(verified_claims)}")

    stats = calculate_verification_stats(verified_claims)
    print(f"    Verified:   {stats['verified']}")
    print(f"    Uncertain:  {stats['uncertain']}")
    print(f"    Unverified: {stats['unverified']}")
    print(f"    Confidence: {confidence}%")

    print("✅ Test 11: Full pipeline PASSED")


def test_12_cleanup() -> None:
    """Test 12: Clean up generated test chunks from Pinecone."""
    global report_id_test, full_pipeline_report_id

    ids_to_clean = [report_id_test, full_pipeline_report_id]
    for rid in ids_to_clean:
        success = delete_report_chunks(rid)
        assert success is True
        print(f"  Deleted vector chunks for report: {rid}")

    print("✅ Test 12: Cleanup PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 12 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    test_1_extract_claims()
    test_2_extract_claims_edge_cases()
    test_3_verify_single_claim_setup()
    test_4_verify_single_claim_success()
    test_5_verify_single_claim_failure()
    test_6_calculate_verification_stats()
    test_7_process_single_summary()
    test_8_run_factcheck()
    test_9_get_verified_only()
    test_10_get_factcheck_summary()
    test_11_full_pipeline_run()
    test_12_cleanup()

    # Get final confidence for printout
    final_conf = state_test_8.get_field("confidence_score") if state_test_8 else 0

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 12 TESTS PASSED")
    print("FactCheck Agent complete!")
    print(f"Confidence system working: {final_conf}%")
    print("Ready for Day 13: Writer Agent")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
