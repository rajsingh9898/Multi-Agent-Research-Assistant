"""Standalone validation script for Day 11 (Summary Agent Part 2).

This script tests:
1. retrieve_chunks_for_question()
2. build_context_from_chunks()
3. build_summary_prompt() - English
4. build_summary_prompt() - Hindi
5. extract_citations_from_summary()
6. summarize_single_question()
7. retrieve_and_summarize()
8. run() - complete Part 1 + Part 2 pipeline
9. Citation quality checks
10. Language test - Hindi
11. Full pipeline integration (Day 8 + Day 9 + Day 10 + Day 11)
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
from agents.summary_agent import (
    retrieve_chunks_for_question,
    build_context_from_chunks,
    build_summary_prompt,
    extract_citations_from_summary,
    summarize_single_question,
    retrieve_and_summarize,
    run
)
from tools.pinecone_tool import delete_report_chunks


def create_state_with_search_results(topic: str) -> AgentMemory:
    """Create a temporary test AgentMemory state initialized with sub-questions and search results."""
    state = AgentMemory(
        report_id=f"test_d11_{int(time.time())}_{topic.replace(' ', '_').lower()[:10]}",
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )
    # Add mock sub_questions
    state.update_state("sub_questions", [
        "What are main benefits of meditation?",
        "How does meditation affect the brain?",
        "What does research say about meditation?"
    ])
    # Add mock search_results with real content
    state.update_state("search_results", [
        {
            "question": "What are main benefits of meditation?",
            "sources": [
                {
                    "title": "Meditation Benefits Study",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/meditation",
                    "content": (
                        "Meditation has been shown to reduce stress hormones by 23% in clinical "
                        "trials. Regular practitioners report improved focus, reduced anxiety, and "
                        "better sleep quality. A 2024 Harvard study found 8 weeks of mindfulness "
                        "meditation restructures the brain's amygdala, reducing stress response "
                        "significantly. "
                    ) * 20,
                    "credibility": "academic",
                    "credibility_score": 95,
                    "credibility_icon": "🎓",
                    "word_count": 400,
                    "sub_question": "What are main benefits of meditation?"
                },
                {
                    "title": "Mindfulness Research 2025",
                    "url": "https://bbc.com/health/meditation",
                    "content": (
                        "Scientific research confirms meditation improves mental health outcomes. "
                        "Studies show 40% reduction in depression symptoms after 6 weeks of practice. "
                        "NHS now recommends meditation as first line treatment for mild anxiety. "
                    ) * 15,
                    "credibility": "news",
                    "credibility_score": 75,
                    "credibility_icon": "📰",
                    "word_count": 300,
                    "sub_question": "What are main benefits of meditation?"
                }
            ],
            "source_count": 2,
            "avg_credibility_score": 85
        },
        {
            "question": "How does meditation affect the brain?",
            "sources": [
                {
                    "title": "Neuroscience of Meditation",
                    "url": "https://nature.com/neuroscience-meditation",
                    "content": (
                        "Neuroimaging studies reveal meditation increases gray matter density in "
                        "prefrontal cortex, associated with decision making and emotional regulation. "
                        "Meditators show 20% thicker cortical regions after 2 years of practice. "
                        "MRI scans show reduced amygdala activity in long-term practitioners. "
                    ) * 20,
                    "credibility": "academic",
                    "credibility_score": 95,
                    "credibility_icon": "🎓",
                    "word_count": 420,
                    "sub_question": "How does meditation affect the brain?"
                }
            ],
            "source_count": 1,
            "avg_credibility_score": 95
        }
    ])
    return state


# Shared states for testing
state_test_1 = None
chunks_test_1 = []
state_test_8 = None
state_test_10 = None
full_pipeline_report_id = "full_pipeline_d11"


def test_1_retrieval() -> None:
    """Test 1: Verify retrieve_chunks_for_question retrieves stored chunks from Pinecone."""
    global state_test_1, chunks_test_1
    state_test_1 = create_state_with_search_results("meditation")
    
    # Store chunks first
    from agents.summary_agent import embed_and_store
    embed_result = asyncio.run(
        embed_and_store(state_test_1, state_test_1.get_field("report_id"))
    )
    assert embed_result["success"] is True
    time.sleep(2)  # Give Pinecone time to index

    chunks_test_1 = retrieve_chunks_for_question(
        question="What are benefits of meditation?",
        report_id=state_test_1.get_field("report_id"),
        top_k=5
    )
    assert isinstance(chunks_test_1, list)
    assert len(chunks_test_1) > 0

    print(f"  Retrieved {len(chunks_test_1)} chunks")
    for chunk in chunks_test_1:
        assert "content" in chunk
        assert "source_url" in chunk
        assert "credibility" in chunk
        assert "score" in chunk
        score = chunk.get("score")
        assert 0.0 <= score <= 1.0
        print(f"    [Score: {score:.4f}] URL: {chunk.get('source_url')[:40]}...")
        
    print("✅ Test 1: Retrieval PASSED")


def test_2_context_building() -> None:
    """Test 2: Verify build_context_from_chunks creates formatted context without duplicates."""
    global chunks_test_1
    if not chunks_test_1:
        # Create fallback mock chunks
        chunks_test_1 = [
            {
                "content": "Meditation restructures the brain.",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/meditation",
                "source_title": "Meditation Benefits Study",
                "credibility": "academic",
                "score": 0.95
            }
        ]

    context, urls = build_context_from_chunks(chunks_test_1, "What are benefits of meditation?")
    assert isinstance(context, str)
    assert len(context) > 0
    assert "Source 1" in context
    assert "https://" in context

    assert isinstance(urls, list)
    assert len(urls) > 0
    # Assert deduplicated list
    assert len(urls) == len(set(urls))

    print(f"  Citations found: {len(urls)}")
    print(f"  Context Preview:\n{context[:200]}...")
    print("✅ Test 2: Context building PASSED")


def test_3_prompt_english() -> None:
    """Test 3: Verify build_summary_prompt generates English instructions."""
    system, user = build_summary_prompt(
        question="What are benefits of meditation?",
        context="[Source 1 - nature.com]\nMeditation helps reduce stress.",
        language="english"
    )
    assert isinstance(system, str) and len(system) > 0
    assert isinstance(user, str) and len(user) > 0
    assert "What are benefits of meditation?" in user
    assert "Source" in user
    assert "cite" in system.lower() or "citation" in system.lower() or "source" in system.lower()
    print("✅ Test 3: Prompt English PASSED")


def test_4_prompt_hindi() -> None:
    """Test 4: Verify build_summary_prompt generates Hindi instructions."""
    system, user = build_summary_prompt(
        question="meditation ke fayde kya hain?",
        context="[Source 1]\nMeditation helps...",
        language="hindi"
    )
    assert isinstance(system, str) and len(system) > 0
    assert isinstance(user, str) and len(user) > 0
    assert "Hindi" in user or "हिन्दी" in user
    print("✅ Test 4: Prompt Hindi PASSED")


def test_5_citation_extraction() -> None:
    """Test 5: Verify extract_citations_from_summary extracts and validates URLs."""
    test_summary = (
        "Meditation reduces stress by 23% [Source: https://pubmed.ncbi.nlm.nih.gov/med]. "
        "Harvard study confirms brain changes [Source: https://harvard.edu/meditation-study]. "
        "NHS recommends it for anxiety [Source: https://nhs.uk/mindfulness]."
    )
    available = [
        "https://pubmed.ncbi.nlm.nih.gov/med",
        "https://harvard.edu/meditation-study",
        "https://nhs.uk/mindfulness"
    ]
    citations = extract_citations_from_summary(test_summary, available)
    assert len(citations) == 3
    for c in citations:
        assert c in available
    
    # Check no duplicate URLs are returned
    test_summary_dup = test_summary + " Duplicate claim [Source: https://nhs.uk/mindfulness]."
    citations_dup = extract_citations_from_summary(test_summary_dup, available)
    assert len(citations_dup) == 3

    print(f"  Citations: {citations}")
    print("✅ Test 5: Citation extraction PASSED")


def test_6_single_summarize() -> None:
    """Test 6: Verify summarize_single_question executes single RAG call with GPT-4o-mini."""
    global state_test_1
    assert state_test_1 is not None

    result = asyncio.run(
        summarize_single_question(
            question="What are benefits of meditation?",
            question_index=1,
            total_questions=3,
            report_id=state_test_1.get_field("report_id"),
            language="english",
            state=state_test_1
        )
    )
    assert result is not None
    assert result["question"] == "What are benefits of meditation?"
    assert len(result["summary"]) > 100
    assert isinstance(result["citations"], list)
    assert result["chunk_count"] > 0
    assert result["word_count"] > 50

    print("\n📝 GENERATED SUMMARY:")
    print(result["summary"])
    print(f"\nCitations: {result['citations']}")
    print(f"Words: {result['word_count']}")
    print(f"Chunks used: {result['chunk_count']}")
    print("✅ Test 6: Single summarization PASSED")


def test_7_retrieve_and_summarize_all() -> None:
    """Test 7: Verify retrieve_and_summarize processes multiple sub-questions."""
    global state_test_1
    assert state_test_1 is not None

    result = asyncio.run(
        retrieve_and_summarize(
            state=state_test_1,
            report_id=state_test_1.get_field("report_id")
        )
    )
    assert result["success"] is True
    assert len(result["summaries"]) >= 1

    summaries = state_test_1.get_field("summaries")
    assert summaries is not None
    assert len(summaries) >= 1

    for s in summaries:
        assert "question" in s
        assert "summary" in s
        assert len(s["summary"]) > 100
        assert isinstance(s["citations"], list)
        assert s["chunk_count"] > 0

    print(f"  Summaries generated: {len(summaries)}")
    print("✅ Test 7: retrieve_and_summarize PASSED")


def test_8_run_full() -> None:
    """Test 8: Verify run() integrates Part 1 and Part 2."""
    global state_test_8
    state_test_8 = create_state_with_search_results("Benefits of exercise")
    
    success = asyncio.run(
        run(state_test_8, state_test_8.get_field("report_id"))
    )
    assert success is True
    assert state_test_8.get_field("pinecone_ready") is True
    assert len(state_test_8.get_field("summaries")) > 0
    assert state_test_8.get_field("current_agent") == "factcheck_agent"

    summaries = state_test_8.get_field("summaries")
    print(f"  run() produced {len(summaries)} summaries")
    print("✅ Test 8: run() complete PASSED")


def test_9_citation_quality() -> None:
    """Test 9: Verify citation format quality across generated summaries."""
    global state_test_8
    assert state_test_8 is not None
    
    summaries = state_test_8.get_field("summaries")
    total_citations = 0

    for idx, s in enumerate(summaries, 1):
        citations = s.get("citations", [])
        total_citations += len(citations)
        print(f"  Summary {idx} has {len(citations)} citations")
        for cite in citations:
            assert cite.startswith("https://")
            assert len(cite) > 10
            assert " " not in cite

    # At least 1 citation per summary on average (since content exists)
    assert total_citations >= len(summaries)
    print(f"  Total citations: {total_citations}")
    print("✅ Test 9: Citation quality PASSED")


def test_10_language_hindi() -> None:
    """Test 10: Verify multi-language support produces Hindi summaries."""
    global state_test_10
    state_test_10 = create_state_with_search_results("meditation benefits")
    state_test_10.update_state("language", "hindi")

    success = asyncio.run(
        run(state_test_10, state_test_10.get_field("report_id"))
    )
    assert success is True
    
    summaries = state_test_10.get_field("summaries")
    assert len(summaries) > 0
    assert summaries[0].get("language") == "hindi"
    print("  Hindi summary preview:")
    print(f"    {summaries[0]['summary'][:200]}...")
    print("✅ Test 10: Hindi language PASSED")


def test_11_full_pipeline_run() -> None:
    """Test 11: Verify integration across Orchestrator, Search, and Summary (Full)."""
    global full_pipeline_report_id
    from agents.orchestrator import start_research

    state = asyncio.run(
        start_research(
            report_id=full_pipeline_report_id,
            topic="Impact of social media on teenagers",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )

    questions = state.get_field("sub_questions")
    search_results = state.get_field("search_results")
    summaries = state.get_field("summaries")
    chunk_stats = state.get_field("chunk_stats")

    assert questions != []
    assert search_results != []
    assert summaries != []
    assert chunk_stats is not None
    assert len(summaries) == len(questions)

    print("\n🔬 FULL PIPELINE D11 RESULTS:")
    print(f"  Questions: {len(questions)}")
    total_sources = sum(r.get("source_count", 0) for r in search_results)
    print(f"  Sources:   {total_sources}")
    print(f"  Chunks:    {chunk_stats.get('total_chunks_stored', 0)}")
    print(f"  Summaries: {len(summaries)}")

    for idx, s in enumerate(summaries, 1):
        print(f"\n  Q{idx}: {s['question'][:60]}...")
        print(f"    Summary: {s['summary'][:150]}...")
        print(f"    Citations count: {len(s['citations'])}")

    print("✅ Test 11: Full pipeline PASSED")


def test_12_cleanup() -> None:
    """Test 12: Clean up generated test vector sets from Pinecone."""
    global state_test_1, state_test_8, state_test_10, full_pipeline_report_id
    
    report_ids = [
        state_test_1.get_field("report_id") if state_test_1 else None,
        state_test_8.get_field("report_id") if state_test_8 else None,
        state_test_10.get_field("report_id") if state_test_10 else None,
        full_pipeline_report_id
    ]

    for rid in report_ids:
        if rid:
            success = delete_report_chunks(rid)
            assert success is True
            print(f"  Deleted vector chunks for report: {rid}")

    print("✅ Test 12: Cleanup PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 11 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    test_1_retrieval()
    test_2_context_building()
    test_3_prompt_english()
    test_4_prompt_hindi()
    test_5_citation_extraction()
    test_6_single_summarize()
    test_7_retrieve_and_summarize_all()
    test_8_run_full()
    test_9_citation_quality()
    test_10_language_hindi()
    test_11_full_pipeline_run()
    test_12_cleanup()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 12 TESTS PASSED")
    print("Summary Agent Complete!")
    print("Part 1: Chunking + Embedding")
    print("Part 2: Retrieval + Summarization")
    print("Ready for Day 12: FactCheck Agent")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
