"""Source credibility helpers
- Provide heuristics to rate sources as Academic/News/Blog/Unknown.
"""

from typing import Dict


def rate_source(url: str, title: str, snippet: str) -> Dict:
    """Return a credibility rating and metadata for a source.
    Placeholder returns Unknown.
    """
    return {"url": url, "title": title, "credibility": "Unknown"}
