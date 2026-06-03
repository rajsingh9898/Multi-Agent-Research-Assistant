"""Writer Agent
- Composes the final report in Markdown with inline citations and multi-language support.
"""

from typing import Dict, List


def compose_report(topic: str, verified_claims: List[Dict], summaries: List[Dict], language: str = "english") -> Dict:
    """Return a report dict containing markdown and metadata.
    Placeholder implementation that returns a simple markdown string.
    """
    md = f"# Research Report: {topic}\n\n"
    for v in verified_claims:
        md += f"## {v.get('sub_question')}\n\n"
        for c in v.get("claims", []):
            md += f"- {c.get('text')} (Confidence: {c.get('confidence')}%)\n"
    return {"topic": topic, "language": language, "markdown": md}
