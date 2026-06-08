"""Standalone Pinecone validation script for Day 5.

Run this from the repository root with:

    c:/Users/Raj Singh/Desktop/multi-agent-research/backend/venv/Scripts/python.exe -m backend.test_pinecone

The script prints a clear pass/fail line for each check and cleans up all test
vectors when it finishes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tools.confidence import calculate_confidence_score, get_confidence_label
from backend.tools.credibility import calculate_average_credibility, rate_source_credibility
from backend.tools.pinecone_tool import delete_report_chunks, get_index_stats, query_relevant_chunks, upsert_source_chunks


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _print_result(name: str, passed: bool, details: str = "") -> None:
    """Print a single test result line."""
    status = "PASS" if passed else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"[{status}] {name}{suffix}")


def main() -> None:
    """Run the five Pinecone validation checks and clean up test vectors."""
    report_id = f"pinecone-test-{uuid4().hex[:12]}"
    content = dedent(
        """
        Pinecone stores semantic chunks so the research agent can retrieve the
        most relevant passages during question answering, summarization, and
        fact-checking. This sample text intentionally repeats the same topic
        several times so the embedding query has useful neighborhood matches.

        The assistant should compare claims across multiple sources, rank source
        credibility, and retrieve evidence that supports or challenges a claim.
        Pinecone makes the retrieval step fast and filterable by report id.
        """
    ).strip()

    urls = [
        "https://www.nature.com/articles/example",
        "https://www.reuters.com/world/example",
        "https://www.hindustantimes.com/example",
        "https://medium.com/example-post",
        "https://unknown-example.invalid/post",
    ]

    stored_count = 0
    try:
        # Test 1: Index stats / health check.
        stats = get_index_stats()
        _print_result("Test 1: Index stats", stats.get("status") != "error", str(stats))
        assert stats.get("status") != "error", stats

        # Test 2: Credibility rating for five different URLs.
        ratings = [rate_source_credibility(url) for url in urls]
        expected_labels = ["Academic", "News", "News", "Blog", "Unknown"]
        observed_labels = [item["label"] for item in ratings]
        _print_result("Test 2: Credibility rating", observed_labels == expected_labels, str(observed_labels))
        assert observed_labels == expected_labels, observed_labels

        # Also validate the average credibility helper while we have the sample data.
        average_credibility = calculate_average_credibility(ratings)
        assert 0 <= average_credibility <= 100, average_credibility

        # Test 3: Store chunks from real content.
        stored_count = upsert_source_chunks(
            content=content,
            source_url="https://www.nature.com/articles/example",
            source_title="Sample Nature Article",
            report_id=report_id,
            sub_question="What does Pinecone store?",
            source_index=0,
            credibility=ratings[0],
        )
        _print_result("Test 3: Store chunks", stored_count > 0, f"stored_count={stored_count}")
        assert stored_count > 0, stored_count

        # Test 4: Query chunks and verify retrieval works.
        results = query_relevant_chunks("How does Pinecone help retrieval?", report_id=report_id, top_k=3)
        _print_result("Test 4: Query chunks", len(results) > 0, f"retrieved={len(results)}")
        assert len(results) > 0, results
        assert all(item.get("report_id") == report_id for item in results), results

        # Confidence helpers are part of Day 5 integration, so validate them too.
        confidence_state = {
            "source_credibility": ratings,
            "verified_claims": [{"verified": True}, {"verified": True}, {"verified": False}],
        }
        confidence_score = calculate_confidence_score(confidence_state)
        confidence_label = get_confidence_label(confidence_score)
        assert 0 <= confidence_score <= 100, confidence_score
        assert confidence_label["label"], confidence_label

        # Test 5: Delete chunks and confirm cleanup succeeded.
        deleted = delete_report_chunks(report_id)
        _print_result("Test 5: Delete chunks", deleted, f"report_id={report_id}")
        assert deleted is True

        print("All Pinecone tests completed successfully.")
    finally:
        # Cleanup should run even if one of the assertions fails.
        try:
            if report_id:
                delete_report_chunks(report_id)
        except Exception:
            pass


if __name__ == "__main__":
    main()