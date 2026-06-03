"""Confidence score helpers
- Compute confidence score (0-100) based on cross-source agreement and credibility.
"""

def compute_confidence(scores: list) -> int:
    """Aggregate a list of numerical evidence scores into a 0-100 confidence."""
    if not scores:
        return 0
    avg = sum(scores) / len(scores)
    return int(max(0, min(100, avg)))
