"""FactCheck Agent
- Extracts claims and cross-verifies them across sources.
- Computes confidence scores (0-100%).
"""

from typing import List, Dict


def verify_summaries(summaries: List[Dict]) -> List[Dict]:
    """Return verified claims with labels and confidence scores.
    Placeholder implementation: marks everything as 'uncertain'.
    """
    verified = []
    for s in summaries:
        verified.append({
            "sub_question": s.get("sub_question"),
            "claims": [
                {"text": s.get("summary"), "label": "uncertain", "confidence": 50}
            ],
        })
    return verified
