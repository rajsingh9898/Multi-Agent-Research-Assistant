"""Agent memory helpers
- Simple in-memory store for agent states (use Firestore for persistence).
"""

from typing import Dict

_AGENT_STORE: Dict[str, Dict] = {}


def save_state(report_id: str, state: Dict):
    """Save or update the agent state for a report."""
    _AGENT_STORE[report_id] = state


def load_state(report_id: str) -> Dict:
    """Load agent state; returns empty dict if not present."""
    return _AGENT_STORE.get(report_id, {})
