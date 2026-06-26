"""Standalone validation script for Day 10 (Summary Agent Part 1).

This script tests:
- search results validation and filtering
- source flattening
- chunking logic (500 words, 50 overlap)
- single source processing (success, skips, failures)
- main embed_and_store pipeline coordination
- Pinecone index validation
- state changes, logs, and statistics mapping
- full integrated pipeline run (Day 8 + Day 9 + Day 10 Part 1)
- cleaning up stored test chunks
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
    validate_search_results,
    get_all_sources_flat,
    process_single_source,
    embed_and_store,
    get_embedding_stats
)
from tools.pinecone_tool import (
    chunk_text,
    get_index_stats,
    delete_report_chunks
)

# Mock search results for testing
mock_search_results = [
    {
        "question": "What is machine learning?",
        "sources": [
            {
                "title": "ML Fundamentals",
                "url": "https://arxiv.org/ml-basics",
                "content": (
                    "Machine learning is a subset of artificial intelligence that enables "
                    "computers to learn from data without being explicitly programmed. It focuses "
                    "on the development of computer programs that can access data and use it to "
                    "learn for themselves. The process of learning begins with observations or data, "
                    "such as examples, direct experience, or instruction, in order to look for "
                    "patterns in data and make better decisions in the future based on the examples "
                    "that we provide. "
                ) + " word " * 400,
                "credibility": "Academic",
                "credibility_score": 95,
                "credibility_icon": "🎓",
                "word_count": 450,
                "sub_question": "What is ML?"
            },
            {
                "title": "ML Tutorial 2025",
                "url": "https://towardsdatascience.com/ml",
                "content": (
                    "In this tutorial we explore the fundamentals of machine learning algorithms "
                    "including supervised and unsupervised learning. Supervised algorithms make "
                    "predictions based on labeled training data, whereas unsupervised algorithms "
                    "find hidden patterns or structures in unlabeled data. Machine learning models "
                    "can be classified into regression, classification, clustering, and dimension "
                    "reduction models. "
                ) + " data " * 300,
                "credibility": "Blog",
                "credibility_score": 50,
                "credibility_icon": "✍️",
                "word_count": 350,
                "sub_question": "What is ML?"
            }
        ],
        "source_count": 2,
        "avg_credibility_score": 72
    },
    {
        "question": "How is deep learning different from ML?",
        "sources": [
            {
                "title": "Deep Learning Explained",
                "url": "https://nature.com/deep-learning",
                "content": (
                    "Deep learning is a subset of machine learning that uses neural networks with "
                    "many layers to learn complex patterns from large amounts of data. While "
                    "traditional machine learning often requires manual feature extraction and selection, "
                    "deep learning networks can automatically discover features from raw data. "
                    "This makes them highly effective for applications such as computer vision, "
                    "natural language processing, and audio recognition, although they require "
                    "significantly more computational resources. "
                ) + " neural " * 400,
                "credibility": "Academic",
                "credibility_score": 95,
                "credibility_icon": "🎓",
                "word_count": 480,
                "sub_question": "How is DL different?"
            }
        ],
        "source_count": 1,
        "avg_credibility_score": 95
    }
]


def create_test_state_with_search_results(topic: str, search_results: list[dict]) -> AgentMemory:
    """Create a temporary test AgentMemory state initialized with search results."""
    state = AgentMemory(
        report_id=f"test_day10_{int(time.time())}",
        topic=topic,
        depth="quick",
        language="english",
        user_id="test_user"
    )
    state.update_state("search_results", search_results)
    return state


def test_1_validation() -> None:
    """Test 1: Verify validate_search_results logic."""
    # 1. Valid results
    state = create_test_state_with_search_results("Valid Results", mock_search_results)
    res = validate_search_results(state)
    assert len(res) == 2

    # 2. Empty results
    state_empty = create_test_state_with_search_results("Empty", [])
    assert validate_search_results(state_empty) == []

    # 3. Filtering empty sources list
    dirty_results = [
        mock_search_results[0],
        {"question": "Empty sources question", "sources": [], "source_count": 0}
    ]
    state_dirty = create_test_state_with_search_results("Dirty", dirty_results)
    res_dirty = validate_search_results(state_dirty)
    assert len(res_dirty) == 1
    print("✅ Test 1: Validation PASSED")


def test_2_flat_sources() -> None:
    """Test 2: Verify get_all_sources_flat flattens nested results."""
    flat = get_all_sources_flat(mock_search_results)
    assert len(flat) == 3
    for idx, item in enumerate(flat):
        assert "sub_question" in item
        assert "global_index" in item
        assert item["global_index"] == idx
    print(f"  Total sources flattened: {len(flat)}")
    print("✅ Test 2: Flatten sources PASSED")


def test_3_chunk_text() -> None:
    """Test 3: Test chunk_text functionality and overlap."""
    # 1. Test with long text (around 1000 words)
    long_text = "word " * 1000
    chunks = chunk_text(long_text, chunk_size=500, overlap=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.split()) < 600

    # Test overlap check (the last 50 words of chunk 0 should be at start of chunk 1)
    # Note: text is just "word word ...". Let's test with a different sequence to verify overlap
    seq_text = " ".join([f"w{i}" for i in range(1000)])
    seq_chunks = chunk_text(seq_text, chunk_size=500, overlap=50)
    if len(seq_chunks) >= 2:
        words_c0 = seq_chunks[0].split()
        words_c1 = seq_chunks[1].split()
        overlap_words = words_c0[-50:]
        for w in overlap_words:
            assert w in seq_chunks[1], f"Overlap word {w} not found in second chunk"

    # 2. Test with short text
    short_text = "word " * 100
    short_chunks = chunk_text(short_text, chunk_size=500, overlap=50)
    assert len(short_chunks) == 1

    # 3. Test with empty string
    empty_chunks = chunk_text("", chunk_size=500, overlap=50)
    assert empty_chunks == []
    print("✅ Test 3: Chunking PASSED")


def test_4_single_source_success() -> None:
    """Test 4: Verify process_single_source success flow."""
    source = mock_search_results[0]["sources"][0]
    state = create_test_state_with_search_results("Single Source Success", mock_search_results)
    
    result = asyncio.run(
        process_single_source(
            source=source,
            source_index=1,
            total_sources=3,
            report_id="test_ps_001",
            state=state
        )
    )
    
    assert result["status"] == "success"
    assert result["chunks"] > 0
    assert result["url"] == source["url"]
    print(f"  Chunks stored: {result['chunks']}")
    print("✅ Test 4: Single source PASSED")


def test_5_single_source_empty() -> None:
    """Test 5: Verify process_single_source gracefully skips empty sources."""
    source_empty = {
        "title": "Empty Source",
        "url": "https://example.com",
        "content": "",
        "credibility": "Unknown",
        "sub_question": "test question"
    }
    state = create_test_state_with_search_results("Single Source Empty", mock_search_results)
    
    result = asyncio.run(
        process_single_source(
            source=source_empty,
            source_index=1,
            total_sources=3,
            report_id="test_empty_001",
            state=state
        )
    )
    
    assert result["status"] == "skipped"
    assert result["chunks"] == 0
    print("✅ Test 5: Empty content PASSED")


# Global placeholder to hold main storage state
test_6_state = None


def test_6_embed_and_store_main() -> None:
    """Test 6: Verify embed_and_store processes mock results."""
    global test_6_state
    test_6_state = create_test_state_with_search_results("Embed Main", mock_search_results)
    
    result = asyncio.run(
        embed_and_store(
            state=test_6_state,
            report_id="test_embed_001"
        )
    )
    
    assert result["success"] is True
    assert result["total_chunks"] > 0
    print(f"  Total chunks stored: {result['total_chunks']}")

    chunk_stats = test_6_state.get_field("chunk_stats")
    assert chunk_stats is not None
    assert chunk_stats["total_chunks_stored"] == result["total_chunks"]
    assert chunk_stats["total_sources_processed"] == 3
    assert chunk_stats["failed_sources"] == 0

    pinecone_ready = test_6_state.get_field("pinecone_ready")
    assert pinecone_ready is True
    print("✅ Test 6: embed_and_store PASSED")


def test_7_pinecone_verification() -> None:
    """Test 7: Verify Pinecone index state has vectors."""
    stats = get_index_stats()
    print(f"  Pinecone total vectors: {stats.get('total_vectors')}")
    assert stats.get("total_vectors", 0) > 0
    assert stats.get("status", "").lower() == "ready"  # Based on get_index_stats response of 'ready'
    print("✅ Test 7: Pinecone has vectors PASSED")
    print("  ⚡ CHECK YOUR PINECONE DASHBOARD NOW")
    print("     You should see vectors > 0")


def test_8_state_logs() -> None:
    """Test 8: Verify logs and thinking logs are populated."""
    global test_6_state
    assert test_6_state is not None
    
    logs = test_6_state.get_field("logs")
    thinking_logs = test_6_state.get_field("thinking_logs")
    
    assert len(logs) > 0
    assert len(thinking_logs) > 0
    
    summary_agent_logged = any(log.get("agent") == "summary_agent" for log in logs)
    assert summary_agent_logged is True
    
    print(f"  Logs: {len(logs)}")
    print(f"  Thinking logs: {len(thinking_logs)}")
    print("✅ Test 8: Logs updated PASSED")


def test_9_embedding_stats() -> None:
    """Test 9: Verify get_embedding_stats output schema."""
    global test_6_state
    assert test_6_state is not None
    
    stats = get_embedding_stats(test_6_state)
    assert "state_chunks" in stats
    assert "pinecone_total_vectors" in stats
    assert "total_sources_processed" in stats
    assert "failed_sources" in stats
    assert "pinecone_status" in stats
    assert "pinecone_ready" in stats
    assert stats["pinecone_ready"] is True
    
    print(f"  Embedding Stats Mapping: {stats}")
    print("✅ Test 9: Embedding stats PASSED")


def test_10_full_pipeline() -> None:
    """Test 10: Verify combined Day 8 + Day 9 + Day 10 pipeline."""
    from agents.orchestrator import start_research
    
    state = asyncio.run(
        start_research(
            report_id="pipeline_d10_test",
            topic="Benefits of meditation",
            depth="quick",
            language="english",
            user_id="test_user"
        )
    )
    
    sub_questions = state.get_field("sub_questions")
    search_results = state.get_field("search_results")
    chunk_stats = state.get_field("chunk_stats")
    
    assert len(sub_questions) == 3
    assert search_results != []
    assert chunk_stats is not None
    assert chunk_stats["total_chunks_stored"] > 0
    assert state.get_field("pinecone_ready") is True

    print("\n🔬 FULL PIPELINE RESULTS:")
    print(f"  Questions: {len(sub_questions)}")
    total_srcs = sum(r.get("source_count", 0) for r in search_results)
    print(f"  Sources searched: {total_srcs}")
    print(f"  Chunks stored: {chunk_stats['total_chunks_stored']}")
    print(f"  Pinecone ready: {state.get_field('pinecone_ready')}")
    print("✅ Test 10: Full pipeline PASSED")


def test_11_cleanup() -> None:
    """Test 11: Clean up generated test chunks from Pinecone."""
    report_ids_to_clean = ["test_ps_001", "test_embed_001", "pipeline_d10_test"]
    for r_id in report_ids_to_clean:
        success = delete_report_chunks(r_id)
        assert success is True
        
    print("✅ Test 11: Cleanup PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 10 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    test_1_validation()
    test_2_flat_sources()
    test_3_chunk_text()
    test_4_single_source_success()
    test_5_single_source_empty()
    test_6_embed_and_store_main()
    test_7_pinecone_verification()
    test_8_state_logs()
    test_9_embedding_stats()
    test_10_full_pipeline()
    test_11_cleanup()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ ALL 11 TESTS PASSED")
    print("Summary Agent Part 1 ready")
    print("Day 11: Add retrieval + summarization")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
