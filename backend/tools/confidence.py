"""Confidence score helpers for research reports.

This module turns the state produced by the multi-agent workflow into a single
0-100 confidence score that is explainable to users and easy to debug.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .credibility import calculate_average_credibility


def _extract_claims(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return claim objects from the agent state in a tolerant format."""
    claims = state.get("verified_claims") or []
    return claims if isinstance(claims, list) else []


def _extract_sources(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return source objects from the agent state in a tolerant format."""
    sources = state.get("source_credibility") or []
    return sources if isinstance(sources, list) else []


def _count_verified_claims(claims: Iterable[Dict[str, Any]]) -> int:
    """Count claims that are explicitly marked as verified or passed."""
    verified = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        status = str(claim.get("status") or claim.get("result") or "").lower()
        if claim.get("verified") is True or claim.get("is_verified") is True:
            verified += 1
        elif status in {"verified", "true", "passed", "confirmed", "supported"}:
            verified += 1
    return verified


def calculate_confidence_score(state: Dict[str, Any]) -> int:
    """Calculate the final confidence score using four weighted factors.

    Factor 1: Source Credibility (30%)
    - High-quality sources increase trust in the report.

    Factor 2: Claim Verification Rate (40%)
    - Claims that are independently verified contribute the most weight.

    Factor 3: Source Count (20%)
    - More sources generally improves confidence until diminishing returns.

    Factor 4: Source Diversity (10%)
    - Multiple domains reduce the risk of relying on a single viewpoint.
    """
    sources = _extract_sources(state)
    claims = _extract_claims(state)

    # Factor 1: average credibility score across all collected sources.
    credibility_score = calculate_average_credibility(sources)

    # Factor 2: percentage of verified claims among the claim set.
    total_claims = len(claims)
    verified_count = _count_verified_claims(claims)
    claim_verification_score = 0.0 if total_claims == 0 else (verified_count / total_claims) * 100.0

    # Factor 3: reward breadth of evidence, capped at five sources.
    unique_source_count = len(
        {
            str(source.get("url") or source.get("source_url") or "").strip()
            for source in sources
            if isinstance(source, dict) and (source.get("url") or source.get("source_url"))
        }
    )
    source_count_score = min(100.0, unique_source_count * 20.0)

    # Factor 4: reward domain diversity, capped at four unique domains.
    unique_domains = {
        str(source.get("domain") or source.get("hostname") or source.get("source_domain") or "").strip().lower()
        for source in sources
        if isinstance(source, dict) and (source.get("domain") or source.get("hostname") or source.get("source_domain"))
    }
    diversity_score = min(100.0, len(unique_domains) * 25.0)

    final_score = (
        credibility_score * 0.30
        + claim_verification_score * 0.40
        + source_count_score * 0.20
        + diversity_score * 0.10
    )

    return int(max(0, min(100, round(final_score))))


def get_confidence_label(score: int) -> Dict[str, Any]:
    """Convert a numeric score into a user-facing confidence descriptor."""
    score = max(0, min(100, int(score)))
    if score >= 80:
        return {
            "label": "High Confidence",
            "color": "green",
            "emoji": "🟢",
            "description": "The report has strong source quality and verification support.",
        }
    if score >= 60:
        return {
            "label": "Moderate Confidence",
            "color": "yellow",
            "emoji": "🟡",
            "description": "The report is useful, but some claims or sources should still be reviewed.",
        }
    if score >= 40:
        return {
            "label": "Low Confidence",
            "color": "orange",
            "emoji": "🟠",
            "description": "The report has limited support and should be treated cautiously.",
        }
    return {
        "label": "Very Low Confidence",
        "color": "red",
        "emoji": "🔴",
        "description": "The report lacks enough verified evidence to be trusted yet.",
    }
