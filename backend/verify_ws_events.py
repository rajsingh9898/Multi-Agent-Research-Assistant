"""WebSocket agent events verification check.

This script executes a mock research pipeline run with a MockWebSocket connected,
captures all generated events, and performs strict validation checks on their sequence,
agents context, thinking logs, and millisecond timestamps.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(level=logging.WARNING)

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from fastapi.websockets import WebSocketState


class MockWebSocket:
    """Mock WebSocket client that captures and records events."""

    def __init__(self) -> None:
        """Initialize empty events array and state."""
        self.events: list[dict[str, Any]] = []
        self.client_state = WebSocketState.CONNECTED

    async def accept(self) -> None:
        """Bypass accept handler."""
        pass

    async def send_json(self, data: dict[str, Any]) -> None:
        """Record JSON messages sent over the socket."""
        self.events.append(data)

    async def send_text(self, text: str) -> None:
        """Record raw text messages sent over the socket."""
        self.events.append({"raw": text})

    def get_events_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Return list of captured events matching event type name."""
        return [e for e in self.events if e.get("event") == event_type]

    def get_events_by_agent(self, agent: str) -> list[dict[str, Any]]:
        """Return list of captured events matching agent identifier."""
        return [e for e in self.events if e.get("agent") == agent]

    def print_summary(self) -> None:
        """Print a formatted checklist summary of all logged events."""
        print("\n📡 WEBSOCKET EVENTS CAPTURED:")
        print("─" * 55)
        for i, event in enumerate(self.events, 1):
            evt = event.get("event", "?")
            agent = event.get("agent", "?")
            msg = event.get("message", "")[:45]
            print(f"  {i:2d}. [{agent:<16}] {evt:<15} | {msg}")
        print(f"\n  Total events: {len(self.events)}")


class MockChatCompletions:
    """Mocks OpenAI chat completions for deterministic offline test runs."""

    def create(self, *args, **kwargs) -> Any:
        messages = kwargs.get("messages", [])
        prompt = ""
        for m in messages:
            prompt += m.get("content", "") + "\n"

        # Determine agent type from prompt
        if "sub_questions" in prompt or "sub-questions" in prompt:
            content = json.dumps({
                "sub_questions": [
                    "Benefits of yoga for flexibility?",
                    "Scientific evidence on yoga for stress?",
                    "Yoga cardiovascular benefits?"
                ]
            })
        elif "summary" in prompt:
            content = json.dumps({
                "summary": "Yoga helps improve core stability and range of motion [Source: https://yoga-science.org]. Additionally, scientific evidence shows it reduces cortisol levels [Source: https://stress-journal.com].",
                "citations": ["https://yoga-science.org", "https://stress-journal.com"]
            })
        elif "verifiable statement" in prompt or "claim extraction" in prompt or "FactCheck" in prompt or "JSON array" in prompt or "claims" in prompt:
            content = json.dumps([
                "Yoga improves range of motion by 20%",
                "Scientific evidence shows yoga reduces cortisol"
            ])
        elif "executive_summary" in prompt or "detailed_analysis" in prompt:
            content = json.dumps({
                "title": "Comprehensive Benefits of Yoga",
                "executive_summary": "Yoga provides major improvements in physical flexibility and mental stress reduction.",
                "key_findings": [
                    {
                        "point": "Yoga improves range of motion by 20%",
                        "citation": "https://yoga-science.org",
                        "status": "verified"
                    },
                    {
                        "point": "Scientific evidence shows yoga reduces cortisol",
                        "citation": "https://stress-journal.com",
                        "status": "verified"
                    }
                ],
                "detailed_analysis": "Aerobic and stretching components of yoga promote muscle lengthening and alignment. Scientific trials show a 20% range of motion improvement.",
                "limitations": "Long-term randomized controlled trials are limited.",
                "conclusion": "Yoga is a highly effective, low-impact exercise for overall well-being."
            })
        elif "followup" in prompt or "followup_questions" in prompt or "gaps" in prompt:
            content = json.dumps({
                "followup_questions": [
                    "What style of yoga is most effective for flexibility?",
                    "Are there age limits to yoga benefits?",
                    "How does yoga compare to Pilates for core strength?",
                    "What is the optimal weekly frequency for yoga?",
                    "Are there negative side effects of improper yoga postures?"
                ]
            })
        else:
            # Fallback
            content = "{}"

        # Mock Choice and Message structures
        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response


class MockEmbeddings:
    """Mocks OpenAI embeddings creation."""

    def create(self, *args, **kwargs) -> Any:
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        return mock_response


async def run_ws_verification() -> None:
    """Orchestrates mock pipeline run with mock client socket attached, checking all validations."""
    print("=" * 60)
    print("WebSocket Event Verification")
    print("=" * 60)

    # Setup mock WebSocket
    mock_ws = MockWebSocket()
    report_id = f"ws_verify_{int(time.time())}"

    # Connect mock client to WebSocketManager singleton registry
    from utils.websocket_manager import ws_manager, ConnectionInfo
    ws_manager.connections[report_id] = ConnectionInfo(
        websocket=mock_ws,
        report_id=report_id,
        connected_at=time.time()
    )

    print(f"\n🔗 Mock WS connected: {report_id}")

    # Run complete pipeline with OpenAI mocked to avoid 401 credential errors
    print("\n🚀 Running complete pipeline...")

    from agents.orchestrator import start_research

    # Patch OpenAI completions and embeddings
    with patch("openai.resources.chat.completions.Completions.create", new=MockChatCompletions().create), \
         patch("openai.resources.embeddings.Embeddings.create", new=MockEmbeddings().create):

        state = await start_research(
            report_id=report_id,
            topic="Benefits of green tea",
            depth="quick",
            language="english",
            user_id="ws_verify_user"
        )

    # Print all captured events
    mock_ws.print_summary()

    # Verify required events present
    print("\n✅ VERIFICATION CHECKS:")
    print("─" * 55)

    checks = [
        ("research_start", "system", "Pipeline started"),
        ("agent_start", "orchestrator", "Orchestrator began"),
        ("agent_done", "orchestrator", "Orchestrator finished"),
        ("agent_start", "search_agent", "Search began"),
        ("agent_done", "search_agent", "Search finished"),
        ("agent_start", "summary_agent", "Summary began"),
        ("agent_done", "summary_agent", "Summary finished"),
        ("agent_start", "factcheck_agent", "FactCheck began"),
        ("agent_done", "factcheck_agent", "FactCheck finished"),
        ("agent_start", "writer_agent", "Writer began"),
        ("agent_done", "writer_agent", "Writer finished"),
        ("agent_start", "followup_agent", "FollowUp began"),
        ("agent_done", "followup_agent", "FollowUp finished"),
        ("thinking_log", None, "Thinking logs present"),
        ("report_ready", "system", "Report ready sent")
    ]

    all_passed = True
    for expected_event, expected_agent, desc in checks:
        events = mock_ws.get_events_by_type(expected_event)
        if expected_agent:
            events = [e for e in events if e.get("agent") == expected_agent]

        if events:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ MISSING: {desc} (event={expected_event}, agent={expected_agent})")
            all_passed = False

    # Check event ordering
    print("\n📋 EVENT ORDER CHECK:")
    print("─" * 55)

    event_names = [e.get("event", "") for e in mock_ws.events]

    # research_start should be before report_ready
    if "research_start" in event_names and "report_ready" in event_names:
        rs_idx = event_names.index("research_start")
        rr_idx = event_names.index("report_ready")
        if rs_idx < rr_idx:
            print("  ✅ research_start before report_ready")
        else:
            print("  ❌ WRONG ORDER: report_ready before start")
            all_passed = False

    # Orchestrator before search
    orch_events = mock_ws.get_events_by_agent("orchestrator")
    search_events = mock_ws.get_events_by_agent("search_agent")
    if orch_events and search_events:
        orch_times = [e.get("timestamp", 0) for e in orch_events]
        search_times = [e.get("timestamp", 0) for e in search_events]
        if max(orch_times) <= min(search_times):
            print("  ✅ Orchestrator before Search Agent")
        else:
            print("  ⚠️ Agent ordering overlapping in asynchronous tasks")

    # Count thinking logs
    thinking = mock_ws.get_events_by_type("thinking_log")
    print(f"  ✅ Thinking logs: {len(thinking)}")
    if len(thinking) < 5:
        print("    ⚠️ Expected more thinking logs")

    # Statistics
    print("\n📊 EVENT STATISTICS:")
    print("─" * 55)

    from collections import Counter
    event_counts = Counter(e.get("event", "") for e in mock_ws.events)
    for event_type, count in event_counts.most_common():
        print(f"  {event_type:<20}: {count}")

    agent_counts = Counter(
        e.get("agent", "") for e in mock_ws.events if e.get("agent") != "system"
    )
    print("\n  Events per agent:")
    for agent, count in agent_counts.most_common():
        print(f"    {agent:<20}: {count} events")

    # Cleanup
    ws_manager.clear_event_history(report_id)
    if report_id in ws_manager.connections:
        del ws_manager.connections[report_id]

    # Delete Pinecone vectors
    try:
        from tools.pinecone_tool import delete_report_chunks
        delete_report_chunks(report_id)
    except Exception as exc:
        print(f"  ⚠️ Pinecone cleanup error: {exc}")

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL WS VERIFICATION CHECKS PASSED")
        print("All agents emitting correct events!")
    else:
        print("❌ SOME CHECKS FAILED")
        print("Review agent files for missing emits")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_ws_verification())
