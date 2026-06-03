"""FollowUp Agent
- Generates smart follow-up research questions based on final report.
"""

from typing import List


def generate_followups(report_md: str) -> List[str]:
    """Return a list of follow-up questions.
    Placeholder uses simple heuristics.
    """
    return ["What are the next experiments to test these claims?", "Which datasets could validate the findings?", "What are policy implications?"]
