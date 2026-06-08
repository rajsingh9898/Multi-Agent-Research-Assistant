"""Source credibility heuristics for research and fact-checking workflows.

The helpers in this module score the trustworthiness of a source URL using
domain allowlists and a simple weighted model that is easy to reason about in
production and easy to debug during research runs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

ACADEMIC_DOMAINS: List[str] = [
    "acm.org",
    "arxiv.org",
    "biorxiv.org",
    "cambridge.org",
    "cell.com",
    "crossref.org",
    "doi.org",
    "frontiersin.org",
    "harvard.edu",
    "ieee.org",
    "ijcai.org",
    "jamanetwork.com",
    "jhu.edu",
    "jstor.org",
    "link.springer.com",
    "mit.edu",
    "nature.com",
    "ncbi.nlm.nih.gov",
    "nejm.org",
    "nih.gov",
    "onlinelibrary.wiley.com",
    "oxfordacademic.com",
    "pnas.org",
    "pubmed.ncbi.nlm.nih.gov",
    "sagepub.com",
    "sciencedirect.com",
    "springer.com",
    "tandfonline.com",
    "wiley.com",
    "wileyonlinelibrary.com",
]

NEWS_DOMAINS: List[str] = [
    "abcnews.go.com",
    "aljazeera.com",
    "apnews.com",
    "bbc.com",
    "bloomberg.com",
    "business-standard.com",
    "cnn.com",
    "deccanherald.com",
    "economictimes.indiatimes.com",
    "firstpost.com",
    "hindustantimes.com",
    "indianexpress.com",
    "indiatoday.in",
    "livemint.com",
    "ndtv.com",
    "news18.com",
    "npr.org",
    "reuters.com",
    "theguardian.com",
    "thehindu.com",
    "timesofindia.indiatimes.com",
    "usatoday.com",
    "washingtonpost.com",
    "wsj.com",
    "forbes.com",
    "cnbc.com",
]

GOVERNMENT_DOMAINS: List[str] = [
    ".gov",
    ".gov.in",
    ".edu",
    ".edu.in",
    ".ac.in",
    ".ac.uk",
    ".ac.jp",
    ".mil",
    ".nic.in",
    ".gov.au",
    ".gov.uk",
    ".gov.sg",
    ".govt.nz",
    ".edu.au",
    ".edu.sg",
    ".gov.ca",
    ".gouv.fr",
    ".go.jp",
]

BLOG_DOMAINS: List[str] = [
    "blogspot.com",
    "dev.to",
    "ghost.io",
    "hashnode.dev",
    "medium.com",
    "substack.com",
    "wordpress.com",
    "tumblr.com",
    "wixsite.com",
    "gitbook.io",
]


def _normalize_hostname(url: str) -> str:
    """Extract a lowercase hostname from any URL-like value."""
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    hostname = (parsed.hostname or "").lower().strip()
    return hostname


def _matches_domain(hostname: str, domain: str) -> bool:
    """Check whether a hostname belongs to a trusted domain entry."""
    if not hostname or not domain:
        return False
    domain = domain.lower().strip()
    if domain.startswith("."):
        return hostname.endswith(domain)
    return hostname == domain or hostname.endswith(f".{domain}")


def _any_domain_match(hostname: str, domains: Iterable[str]) -> bool:
    """Return True when a hostname matches at least one trusted domain."""
    return any(_matches_domain(hostname, domain) for domain in domains)


def rate_source_credibility(url: str) -> Dict[str, Any]:
    """Rate a source URL and return a structured credibility payload.

    Returns a compact object with human-friendly label, numeric score, color,
    and emoji so the frontend can display it directly without extra mapping.
    """
    hostname = _normalize_hostname(url)
    if not hostname:
        return {
            "url": url,
            "domain": "",
            "rating": "Unknown",
            "score": 40,
            "label": "Unknown",
            "color": "gray",
            "emoji": "❔",
        }

    if _any_domain_match(hostname, GOVERNMENT_DOMAINS):
        return {
            "url": url,
            "domain": hostname,
            "rating": "Government",
            "score": 90,
            "label": "Government",
            "color": "green",
            "emoji": "🏛️",
        }

    if _any_domain_match(hostname, ACADEMIC_DOMAINS):
        return {
            "url": url,
            "domain": hostname,
            "rating": "Academic",
            "score": 95,
            "label": "Academic",
            "color": "green",
            "emoji": "🎓",
        }

    if _any_domain_match(hostname, NEWS_DOMAINS):
        return {
            "url": url,
            "domain": hostname,
            "rating": "News",
            "score": 75,
            "label": "News",
            "color": "blue",
            "emoji": "📰",
        }

    if _any_domain_match(hostname, BLOG_DOMAINS) or "blog" in hostname or "medium" in hostname or "substack" in hostname:
        return {
            "url": url,
            "domain": hostname,
            "rating": "Blog",
            "score": 50,
            "label": "Blog",
            "color": "yellow",
            "emoji": "✍️",
        }

    return {
        "url": url,
        "domain": hostname,
        "rating": "Unknown",
        "score": 40,
        "label": "Unknown",
        "color": "gray",
        "emoji": "❔",
    }


def calculate_average_credibility(sources: List[Dict[str, Any]]) -> float:
    """Return the average credibility score for a list of source payloads."""
    if not sources:
        return 0.0

    scores: List[float] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        score = source.get("score")
        if score is None:
            score = source.get("credibility_score")
        if score is None and isinstance(source.get("credibility"), dict):
            score = source["credibility"].get("score")
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            continue

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)
