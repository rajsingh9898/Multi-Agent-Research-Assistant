"""Standalone Tavily Search Tool validation script.

Run this from the repository root with:

    backend/venv/Scripts/python backend/test_tavily.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Set project root in path to allow imports of backend packages
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load backend's local environment file
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from backend.tools.tavily_tool import (
    initialize_tavily,
    search,
    filter_results,
    format_results,
    search_for_question,
    search_all_questions,
    get_search_summary
)


def _print_result(test_num: int, name: str, passed: bool, details: str = "") -> None:
    """Print a formatted PASS/FAIL status line for a test."""
    status = "PASS" if passed else "FAIL"
    suffix = f" - {details}" if details else ""
    print(f"[Test {test_num}] [{status}] {name}{suffix}")


def main() -> None:
    """Execute all 8 Tavily search tool tests."""
    print("=" * 60)
    print("STARTING TAVILY SEARCH TOOL TESTS (DAY 6)")
    print("=" * 60)

    # ----------------------------------------------------
    # Test 1: Initialize Tavily
    # ----------------------------------------------------
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        client = initialize_tavily()
        t1_passed = client is not None and api_key is not None
        _print_result(1, "Initialize Tavily", t1_passed, f"API key loaded: {api_key[:12] if api_key else 'None'}...")
        assert t1_passed, "Tavily client failed to initialize or API Key not found."
    except Exception as e:
        _print_result(1, "Initialize Tavily", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 2: Search "AI in healthcare 2025"
    # ----------------------------------------------------
    try:
        query = "AI in healthcare 2025"
        results = search(query, max_results=3, search_depth="basic")
        
        # Verify 1-4 results (allowing some flexibility if Tavily returns fewer but at least some)
        t2_passed = len(results) > 0
        details = f"Returned {len(results)} results"
        
        # Check standard keys
        if t2_passed:
            for item in results:
                assert "title" in item, "Missing title in search result"
                assert "url" in item, "Missing url in search result"
                assert "content" in item, "Missing content in search result"
                assert 0.0 <= item.get("score", 0.0) <= 1.0, f"Score out of bounds: {item.get('score')}"
            
            # Print first result content as proof of search working
            details += f" | Top URL: {results[0].get('url')}"

        _print_result(2, f"Search '{query}'", t2_passed, details)
        assert t2_passed, "No results returned for search query."
    except Exception as e:
        _print_result(2, "Search AI in Healthcare", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 3: Search "LangChain agents tutorial" (Print Credibility)
    # ----------------------------------------------------
    try:
        query = "LangChain agents tutorial"
        results = search(query, max_results=3, search_depth="basic")
        formatted = format_results(results, query)
        
        t3_passed = len(formatted) > 0
        details = ""
        if t3_passed:
            cred_str = []
            for item in formatted:
                assert "credibility" in item, "Missing credibility rating"
                assert "credibility_score" in item, "Missing credibility score"
                cred_str.append(f"{item.get('url')[:30]} ({item.get('credibility')})")
            details = " | ".join(cred_str)

        _print_result(3, f"Search '{query}' Credibility", t3_passed, details)
        assert t3_passed, "Failed to format and fetch credibility scores."
    except Exception as e:
        _print_result(3, "Search LangChain agents tutorial", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 4: Search "Python FastAPI websocket" (Print Word Counts)
    # ----------------------------------------------------
    try:
        query = "Python FastAPI websocket"
        results = search(query, max_results=3, search_depth="basic")
        formatted = format_results(results, query)
        
        t4_passed = len(formatted) > 0
        details = ""
        if t4_passed:
            wc_str = []
            for item in formatted:
                assert "word_count" in item, "Missing word count field"
                wc_str.append(f"{item.get('url')[:30]} ({item.get('word_count')} words)")
            details = " | ".join(wc_str)

        _print_result(4, f"Search '{query}' Word Counts", t4_passed, details)
        assert t4_passed, "Failed to calculate word counts."
    except Exception as e:
        _print_result(4, "Search Python FastAPI websocket", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 5: Filter Test
    # ----------------------------------------------------
    try:
        mock_results = [
            {
                "title": "Good Result 1", 
                "url": "https://www.nature.com/article1", 
                "content": "This is a very good article from nature that has more than one hundred characters of content so it should not be filtered.", 
                "score": 0.85
            },
            {
                "title": "Low Score Result", 
                "url": "https://example.com/low-score", 
                "content": "This article has more than one hundred characters of content but its score is extremely low and therefore should be filtered.", 
                "score": 0.25
            },
            {
                "title": "Short Content Result", 
                "url": "https://example.com/short", 
                "content": "Too short.", 
                "score": 0.90
            },
            {
                "title": "Blocked Domain Result", 
                "url": "https://reddit.com/r/ai", 
                "content": "This is a post on reddit which is a blocked domain in our list of social media/forums and should be filtered.", 
                "score": 0.95
            },
            {
                "title": "Duplicate Url Result", 
                "url": "https://www.nature.com/article1", 
                "content": "This is another description of the first article with duplicate url and should be filtered.", 
                "score": 0.88
            }
        ]

        filtered = filter_results(mock_results)
        t5_passed = len(filtered) == 1 and filtered[0]["title"] == "Good Result 1"
        details = f"Retained {len(filtered)} results (Expected 1: Good Result 1)"
        
        _print_result(5, "Filter Test (mock items)", t5_passed, details)
        assert t5_passed, f"Filtering did not return exactly the one valid good result. Got: {[i['title'] for i in filtered]}"
    except Exception as e:
        _print_result(5, "Filter Test", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 6: Full Pipeline Test
    # ----------------------------------------------------
    try:
        query = "What are the latest AI research tools?"
        report_id = "test-report-123"
        
        # Override / clear REPORT_STORE mock
        from main import REPORT_STORE
        REPORT_STORE[report_id] = {
            "report_id": report_id,
            "thinking_logs": []
        }

        output = search_for_question(query, report_id)
        
        # Validation checks on returned pipeline structure
        assert output["question"] == query, "Question mismatch"
        assert isinstance(output["sources"], list), "sources is not a list"
        assert output["source_count"] == len(output["sources"]), "source_count mismatch"
        assert isinstance(output["avg_credibility_score"], int), "avg_credibility_score is not an int"
        
        # Ensure thinking logs updated
        assert len(REPORT_STORE[report_id]["thinking_logs"]) > 0, "No thinking logs recorded"
        
        # Inspect sources format
        t6_passed = True
        details = f"Sources count: {output['source_count']} | Avg Credibility: {output['avg_credibility_score']}"
        if output["source_count"] > 0:
            sample = output["sources"][0]
            assert "credibility_label" in sample
            assert "credibility_icon" in sample
            assert "sub_question" in sample
            details += f" | First source: {sample['url']} ({sample['credibility_label']})"
            
        _print_result(6, "Full Pipeline (search_for_question)", t6_passed, details)
        assert t6_passed, "Pipeline output format failed assertions."
    except Exception as e:
        _print_result(6, "Full Pipeline Test", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 7: Error Handling Test
    # ----------------------------------------------------
    try:
        # 1. Empty string
        empty_res = search("", max_results=4)
        assert empty_res == [], f"Empty search should return [], got {empty_res}"
        
        # 2. Too long query
        long_query = "FastAPI websocket tutorial " * 30  # ~750 chars
        long_res = search(long_query, max_results=2)
        
        t7_passed = empty_res == [] and isinstance(long_res, list)
        _print_result(7, "Error Handling (Empty/Long query)", t7_passed, f"Empty query -> [], Long query -> {len(long_res)} results")
        assert t7_passed, "Error handling check failed."
    except Exception as e:
        _print_result(7, "Error Handling Test", False, f"Exception: {e}")
        raise e

    # ----------------------------------------------------
    # Test 8: search_all_questions Test
    # ----------------------------------------------------
    try:
        questions = ["What is FastAPI?", "What is Tavily?"]
        report_id = "test-report-multi"
        
        from main import REPORT_STORE
        REPORT_STORE[report_id] = {
            "report_id": report_id,
            "thinking_logs": []
        }

        # Keep short to save API quota, delay should sleep 1s between
        start_time = time.time()
        all_results = search_all_questions(questions, report_id)
        elapsed = time.time() - start_time
        
        assert len(all_results) == len(questions), f"Expected {len(questions)} results, got {len(all_results)}"
        assert elapsed >= 1.0, f"Expected search delay of at least 1.0s, elapsed time was {elapsed:.2f}s"
        
        summary = get_search_summary(all_results)
        
        # Assertions on summary
        assert summary["total_questions"] == 2
        assert isinstance(summary["total_sources"], int)
        assert isinstance(summary["avg_credibility"], int)
        assert "credibility_breakdown" in summary
        assert len(summary["top_sources"]) <= 3

        t8_passed = True
        details = (
            f"Elapsed: {elapsed:.2f}s | Questions: {summary['total_questions']} | "
            f"Sources: {summary['total_sources']} | Avg Credibility: {summary['avg_credibility']} | "
            f"Top unique sources count: {len(summary['top_sources'])}"
        )
        _print_result(8, "search_all_questions with delay + Summary", t8_passed, details)
        assert t8_passed, "Multi-question pipeline failed assertions."
    except Exception as e:
        _print_result(8, "search_all_questions Test", False, f"Exception: {e}")
        raise e

    print("=" * 60)
    print("ALL 8 TAVILY SEARCH TOOL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
