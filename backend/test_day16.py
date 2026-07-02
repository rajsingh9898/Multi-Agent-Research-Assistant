"""Unit and integration test suite for Day 16 (WebSocket Integration).

This script tests the enhanced WebSocketManager class and its shortcuts, telemetry,
history replay queue, broken connection tolerance, and active pipeline triggers.
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
from utils.websocket_manager import WebSocketManager, ConnectionInfo


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


def test_1_websocket_manager_initialization() -> None:
    """Test 1: Verify WebSocketManager initial parameters."""
    manager = WebSocketManager()
    assert manager.connections == {}
    assert manager.get_connected_count() == 0
    assert manager.is_connected("test") is False
    print("✅ Test 1: Initialization PASSED")


def test_2_connect_disconnect() -> None:
    """Test 2: Verify connect and disconnect functionality."""
    manager = WebSocketManager()
    mock_ws = MockWebSocket()

    asyncio.run(manager.connect(mock_ws, "test_report_1"))

    assert manager.is_connected("test_report_1") is True
    assert manager.get_connected_count() == 1

    connected_events = mock_ws.get_events_by_type("connected")
    assert len(connected_events) == 1
    assert connected_events[0]["data"]["report_id"] == "test_report_1"

    asyncio.run(manager.disconnect("test_report_1"))
    assert manager.is_connected("test_report_1") is False
    assert manager.get_connected_count() == 0
    print("✅ Test 2: Connect/disconnect PASSED")


def test_3_emit_sends_correct_format() -> None:
    """Test 3: Verify emit format contains required fields."""
    manager = WebSocketManager()
    mock_ws = MockWebSocket()
    asyncio.run(manager.connect(mock_ws, "test_emit"))

    asyncio.run(manager.emit(
        report_id="test_emit",
        event="agent_start",
        agent="orchestrator",
        message="Test message",
        data={"key": "value"}
    ))

    events = mock_ws.get_events_by_type("agent_start")
    assert len(events) == 1
    evt = events[0]
    assert evt["event"] == "agent_start"
    assert evt["agent"] == "orchestrator"
    assert evt["message"] == "Test message"
    assert evt["data"]["key"] == "value"
    assert "timestamp" in evt
    assert isinstance(evt["timestamp"], int)
    print("✅ Test 3: emit() format PASSED")


def test_4_emit_when_not_connected() -> None:
    """Test 4: Verify emit behavior when the target client is not connected."""
    manager = WebSocketManager()

    result = asyncio.run(manager.emit(
        report_id="not_connected_123",
        event="test_event",
        agent="system",
        message="Test"
    ))

    assert result is False

    history = manager.get_event_history("not_connected_123")
    assert len(history) == 1
    assert history[0]["event"] == "test_event"
    print("✅ Test 4: emit() when disconnected PASSED")


def test_5_event_history_storage() -> None:
    """Test 5: Verify history event queueing and replay on client connection."""
    manager = WebSocketManager()
    report_id = "history_test"

    # Emit events without connection
    for i in range(5):
        asyncio.run(manager.emit(
            report_id=report_id,
            event=f"test_event_{i}",
            agent="system",
            message=f"Event {i}"
        ))

    history = manager.get_event_history(report_id)
    assert len(history) == 5

    # Connect client - should trigger replay of all history
    mock_ws = MockWebSocket()
    asyncio.run(manager.connect(mock_ws, report_id))

    # Expect: 1 connect event + 5 replayed history events = 6 events total
    assert len(mock_ws.events) >= 6

    manager.clear_event_history(report_id)
    assert manager.get_event_history(report_id) == []
    print("✅ Test 5: Event history PASSED")


def test_6_emit_shortcuts() -> None:
    """Test 6: Verify all emit shortcuts formatting layouts."""
    manager = WebSocketManager()
    mock_ws = MockWebSocket()
    asyncio.run(manager.connect(mock_ws, "shortcut_test"))

    asyncio.run(manager.emit_agent_start("shortcut_test", "test_agent", "Starting"))
    asyncio.run(manager.emit_agent_update("shortcut_test", "test_agent", "Progress", {"pct": 50}))
    asyncio.run(manager.emit_agent_done("shortcut_test", "test_agent", "Done", {"result": "ok"}))
    asyncio.run(manager.emit_thinking("shortcut_test", "test_agent", "I am thinking..."))
    asyncio.run(manager.emit_error("shortcut_test", "test_agent", "Something failed"))
    asyncio.run(manager.emit_report_ready("shortcut_test"))

    assert len(mock_ws.get_events_by_type("agent_start")) == 1
    assert len(mock_ws.get_events_by_type("agent_update")) == 1
    assert len(mock_ws.get_events_by_type("agent_done")) == 1
    assert len(mock_ws.get_events_by_type("thinking_log")) == 1
    assert len(mock_ws.get_events_by_type("error")) == 1
    assert len(mock_ws.get_events_by_type("report_ready")) == 1

    thinking_event = mock_ws.get_events_by_type("thinking_log")[0]
    assert thinking_event["data"]["thought"] == "I am thinking..."
    print("✅ Test 6: All emit shortcuts PASSED")


def test_7_multiple_concurrent_connections() -> None:
    """Test 7: Verify multiple simultaneous connection registries and broadcast triggers."""
    manager = WebSocketManager()
    report_ids = ["concurrent_1", "concurrent_2", "concurrent_3"]
    mock_sockets = {}

    for rid in report_ids:
        mock_ws = MockWebSocket()
        mock_sockets[rid] = mock_ws
        asyncio.run(manager.connect(mock_ws, rid))

    assert manager.get_connected_count() == 3

    # Broadcast message to all connections
    sent = asyncio.run(manager.broadcast(
        event="system_message",
        message="Hello all connections"
    ))

    assert sent == 3
    for mock_ws in mock_sockets.values():
        assert len(mock_ws.get_events_by_type("system_message")) == 1

    # Disconnect all
    for rid in report_ids:
        asyncio.run(manager.disconnect(rid))

    assert manager.get_connected_count() == 0
    print("✅ Test 7: Concurrent connections PASSED")


def test_8_get_connection_stats() -> None:
    """Test 8: Verify connections telemetry stats tracking."""
    manager = WebSocketManager()
    mock_ws = MockWebSocket()
    asyncio.run(manager.connect(mock_ws, "stats_test"))

    asyncio.run(manager.emit_agent_start("stats_test", "orchestrator", "Test"))

    stats = manager.get_connection_stats()
    assert "active_connections" in stats
    assert stats["active_connections"] == 1
    assert "connections" in stats
    assert len(stats["connections"]) == 1

    conn = stats["connections"][0]
    assert "report_id" in conn
    assert "events_sent" in conn
    assert conn["events_sent"] >= 1

    asyncio.run(manager.disconnect("stats_test"))
    print("✅ Test 8: Connection stats PASSED")


def test_9_disconnected_client_handling() -> None:
    """Test 9: Verify disconnected/broken client handling throws no exceptions."""
    manager = WebSocketManager()

    class BrokenWebSocket(MockWebSocket):
        async def send_json(self, data: dict[str, Any]) -> None:
            raise Exception("Connection broken")

    broken_ws = BrokenWebSocket()
    asyncio.run(manager.connect(broken_ws, "broken_test"))

    assert manager.is_connected("broken_test") is True

    result = asyncio.run(manager.emit("broken_test", "test_evt", "system", "Test"))

    # Emit returns False (send failed), connection was auto-pruned
    assert result is False
    assert manager.is_connected("broken_test") is False
    print("✅ Test 9: Broken connection PASSED")


def test_10_full_pipeline_event_verification() -> None:
    """Test 10: Verify the events emitted during a full orchestrator agent run."""
    print("\nRunning full pipeline event test...")
    print("(This takes 60+ seconds)")

    manager = WebSocketManager()
    mock_ws = MockWebSocket()
    report_id = f"full_ws_test_{int(time.time())}"

    # Use global singleton manager during E2E trigger
    from utils.websocket_manager import ws_manager
    ws_manager.connections[report_id] = ConnectionInfo(
        websocket=mock_ws,
        report_id=report_id,
        connected_at=time.time()
    )

    from agents.orchestrator import start_research

    # Patch OpenAI completions and embeddings to run pipeline offline/locally
    with patch("openai.resources.chat.completions.Completions.create", new=MockChatCompletions().create), \
         patch("openai.resources.embeddings.Embeddings.create", new=MockEmbeddings().create):

        asyncio.run(start_research(
            report_id=report_id,
            topic="Benefits of yoga",
            depth="quick",
            language="english",
            user_id="test_user"
        ))

    # Check required events present
    required = ["research_start", "report_ready", "thinking_log"]
    for event_type in required:
        events = mock_ws.get_events_by_type(event_type)
        assert len(events) > 0, f"{event_type} event was not generated by agents!"

    # Verify report_ready is the last meaningful event (excluding connected)
    all_events = mock_ws.events
    last_event = [e for e in all_events if e.get("event") != "connected"][-1]
    assert last_event["event"] == "report_ready"

    # Check timestamps are monotonically increasing (chronological)
    timestamps = [e.get("timestamp", 0) for e in all_events]
    assert timestamps == sorted(timestamps)

    total = len(all_events)
    thinking = len(mock_ws.get_events_by_type("thinking_log"))

    print(f"  Total events: {total}")
    print(f"  Thinking logs: {thinking}")
    mock_ws.print_summary()

    # Cleanup
    from tools.pinecone_tool import delete_report_chunks
    try:
        delete_report_chunks(report_id)
    except Exception as exc:
        print(f"  ⚠️ Pinecone cleanup error: {exc}")

    ws_manager.clear_event_history(report_id)
    if report_id in ws_manager.connections:
        del ws_manager.connections[report_id]

    print("✅ Test 10: Full pipeline events PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 16 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        test_1_websocket_manager_initialization()
        test_2_connect_disconnect()
        test_3_emit_sends_correct_format()
        test_4_emit_when_not_connected()
        test_5_event_history_storage()
        test_6_emit_shortcuts()
        test_7_multiple_concurrent_connections()
        test_8_get_connection_stats()
        test_9_disconnected_client_handling()
        test_10_full_pipeline_event_verification()

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ ALL 10 TESTS PASSED")
        print("WebSocket Integration complete!")
        print("Ready for Day 17: Frontend Input Page")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    except Exception as exc:
        import traceback
        print(f"❌ TEST FAILED: {exc}")
        traceback.print_exc()
        sys.exit(1)
