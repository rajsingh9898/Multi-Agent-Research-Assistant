"""Orchestrator Agent
- Breaks the user topic into sub-questions based on requested depth.
- Placeholder implementation; real logic will call GPT-4o.
"""

from typing import List


def generate_sub_questions(topic: str, depth: str) -> List[str]:
    """Return a list of sub-questions for the given topic and depth.
    This is a simple placeholder used by the starter project.
    """
    if depth == "quick":
        return [f"What is the core idea behind {topic}?", f"Why does {topic} matter?"]
    if depth == "deep":
        return [
            f"Historical context of {topic}",
            f"Key methodologies used in {topic}",
            f"Open problems and limitations for {topic}",
        ]
    return [f"Comprehensive overview of {topic}", f"Latest research directions for {topic}"]
