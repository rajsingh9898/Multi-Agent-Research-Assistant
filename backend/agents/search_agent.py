"""Search Agent
- Calls external search APIs (Tavily) to collect sources for each sub-question.
- Rates credibility (Academic/News/Blog/Unknown).
- Placeholder functions for integration.
"""

from typing import List, Dict


def search_sub_questions(sub_questions: List[str]) -> List[Dict]:
    """Return a list of search result dicts for each sub-question.
    Each dict should include url, title, snippet, and credibility rating.
    """
    results = []
    for q in sub_questions:
        results.append({
            "sub_question": q,
            "sources": [
                {"url": "https://example.com/article1", "title": "Example Article", "snippet": "...", "credibility": "Unknown"}
            ],
        })
    return results
