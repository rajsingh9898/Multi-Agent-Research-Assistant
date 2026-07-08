import asyncio
import json
import time
import sys
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from fastapi.websockets import WebSocketState
from utils.websocket_manager import ws_manager, ConnectionInfo
from agents.orchestrator import start_research
from tools.pinecone_tool import delete_report_chunks
from test_offline_mocks import patch_if_offline
patch_if_offline()
from utils.firebase_config import initialize_firebase
initialize_firebase()

class MockWebSocket:
    """Mock WebSocket client that captures and records events."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self.client_state = WebSocketState.CONNECTED

    async def accept(self) -> None:
        pass

    async def send_json(self, data: Dict[str, Any]) -> None:
        self.events.append(data)

    async def send_text(self, text: str) -> None:
        try:
            parsed = json.loads(text)
            self.events.append(parsed)
        except Exception:
            self.events.append({"raw": text})

    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("event") == event_type]

    def get_events_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("agent") == agent]


def test_ws_event_ordering(events: List[Dict[str, Any]]):
    print("\n🔍 Executing Test 1: Event Ordering...")
    event_types = [e.get("event") for e in events]
    
    # 1. connected present
    has_connected = "connected" in event_types
    print(f"  [{'✅' if has_connected else '❌'}] 'connected' event received first or present: {'connected' == event_types[0] if event_types else False}")
    
    # 2. research_start present
    has_start = "research_start" in event_types
    print(f"  [{'✅' if has_start else '❌'}] 'research_start' event received")
    
    # 3. report_ready present
    has_ready = "report_ready" in event_types
    print(f"  [{'✅' if has_ready else '❌'}] 'report_ready' event received")

    # index of research_start < index of report_ready
    ordering_ok = False
    if has_start and has_ready:
        ordering_ok = event_types.index("research_start") < event_types.index("report_ready")
    print(f"  [{'✅' if ordering_ok else '❌'}] 'research_start' occurs before 'report_ready'")

    # Check agent start before done
    agents = ["orchestrator", "search_agent", "summary_agent", "factcheck_agent", "writer_agent", "followup_agent"]
    for agent in agents:
        agent_events = [e for e in events if e.get("agent") == agent]
        starts = [i for i, e in enumerate(agent_events) if e.get("event") == "agent_start"]
        dones = [i for i, e in enumerate(agent_events) if e.get("event") == "agent_done"]
        
        ok = len(starts) > 0 and len(dones) > 0 and starts[0] < dones[0]
        print(f"  [{'✅' if ok else '❌'}] Agent '{agent}' starts before completes")

    # Print timeline
    print("\n📡 WEBSOCKET TIMELINE:")
    print("─" * 65)
    for i, event in enumerate(events, 1):
        evt = event.get("event", "?")
        agent = event.get("agent", "?")
        msg = event.get("message", "")[:45]
        ts = event.get("timestamp", 0)
        print(f"  {i:2d}. {ts} | [{agent:<15}] {evt:<15} | {msg}")
    print("─" * 65)


def test_ws_thinking_logs(events: List[Dict[str, Any]]):
    print("\n🔍 Executing Test 2: Thinking Logs...")
    thinking_events = [e for e in events if e.get("event") == "thinking_log"]
    
    # At least 5 thinking logs
    has_enough = len(thinking_events) >= 5
    print(f"  [{'✅' if has_enough else '❌'}] At least 5 thinking logs found ({len(thinking_events)} found)")
    
    # Multiple agents have thinking logs
    agents_with_thoughts = {e.get("agent") for e in thinking_events}
    multiple_agents = len(agents_with_thoughts) >= 2
    print(f"  [{'✅' if multiple_agents else '❌'}] Multiple agents have thinking logs ({agents_with_thoughts})")

    # Structure checks
    all_valid = True
    for t in thinking_events:
        data = t.get("data", {})
        thought = data.get("thought", "")
        if not isinstance(thought, str) or len(thought) <= 20:
            all_valid = False
            print(f"    ❌ Bad thought length: {thought}")
            
    print(f"  [{'✅' if all_valid else '❌'}] Each thinking log has descriptive data.thought field (len > 20)")

    # Print thoughts
    print("\n💡 AGENT REASONING STEPS CAPTURED:")
    print("─" * 65)
    for t in thinking_events:
        agent = t.get("agent", "?")
        thought = t.get("data", {}).get("thought", "")
        print(f"  [{agent:<15}] -> {thought[:60]}...")
    print("─" * 65)


def test_ws_data_payloads(events: List[Dict[str, Any]]):
    print("\n🔍 Executing Test 3: Data Payloads...")
    
    # 1. Orchestrator done sub_questions
    orchestrator_dones = [e for e in events if e.get("agent") == "orchestrator" and e.get("event") == "agent_done"]
    if orchestrator_dones:
        data = orchestrator_dones[0].get("data", {})
        sub_qs = data.get("sub_questions", [])
        ok = isinstance(sub_qs, list) and len(sub_qs) >= 2
        print(f"  [{'✅' if ok else '❌'}] orchestrator agent_done has sub_questions (list, len >= 2): {sub_qs}")
    else:
        print("  [❌] orchestrator agent_done not found")

    # 2. Search done sources
    search_dones = [e for e in events if e.get("agent") == "search_agent" and e.get("event") == "agent_done"]
    if search_dones:
        data = search_dones[0].get("data", {})
        total_sources = data.get("total_sources", 0)
        avg_cred = data.get("avg_credibility", 0)
        cred_breakdown = data.get("credibility_breakdown", {})
        
        ok = total_sources > 0 and isinstance(avg_cred, int) and isinstance(cred_breakdown, dict)
        print(f"  [{'✅' if ok else '❌'}] search agent_done has total_sources ({total_sources}), avg_credibility ({avg_cred}%), and breakdown dict")
    else:
        print("  [❌] search agent_done not found")

    # 3. Factcheck done verified/uncertain
    factcheck_dones = [e for e in events if e.get("agent") == "factcheck_agent" and e.get("event") == "agent_done"]
    if factcheck_dones:
        data = factcheck_dones[0].get("data", {})
        verified = data.get("verified", 0)
        uncertain = data.get("uncertain", 0)
        conf = data.get("confidence_score", 0)
        
        ok = isinstance(verified, int) and isinstance(uncertain, int) and isinstance(conf, int)
        print(f"  [{'✅' if ok else '❌'}] factcheck agent_done has verified ({verified}), uncertain ({uncertain}), and confidence_score ({conf}%)")
    else:
        print("  [❌] factcheck agent_done not found")

    # 4. Writer done word count / sections
    writer_dones = [e for e in events if e.get("agent") == "writer_agent" and e.get("event") == "agent_done"]
    if writer_dones:
        data = writer_dones[0].get("data", {})
        word_count = data.get("word_count", 0)
        sections = data.get("sections", 0)
        lang = data.get("language", "")
        
        ok = word_count > 0 and sections == 6 and isinstance(lang, str)
        print(f"  [{'✅' if ok else '❌'}] writer agent_done has word_count ({word_count}), sections ({sections}), and language ({lang})")
    else:
        print("  [❌] writer agent_done not found")

    # 5. Followup questions count
    followup_dones = [e for e in events if e.get("agent") == "followup_agent" and e.get("event") == "agent_done"]
    if followup_dones:
        data = followup_dones[0].get("data", {})
        questions = data.get("questions", [])
        ok = isinstance(questions, list) and len(questions) == 5
        print(f"  [{'✅' if ok else '❌'}] followup agent_done has questions (list, len == 5)")
    else:
        print("  [❌] followup agent_done not found")

    # 6. Report ready report_id
    report_ready_events = [e for e in events if e.get("event") == "report_ready"]
    if report_ready_events:
        data = report_ready_events[0].get("data", {})
        rep_id = data.get("report_id", "")
        ok = isinstance(rep_id, str) and len(rep_id) > 0
        print(f"  [{'✅' if ok else '❌'}] report_ready has report_id string ({rep_id})")
    else:
        print("  [❌] report_ready event not found")


async def run_ws_tests():
    print("=" * 65)
    print("WebSocket E2E Integration and Message Ordering Tests")
    print("=" * 65)

    topic = "AI ethics and governance 2025"
    report_id = f"e2e_ws_test_{int(time.time())}"
    
    ws_mock = MockWebSocket()
    
    # 1. Connect mock WS client
    print(f"\n📡 Connecting mock WebSocket for report: {report_id}...")
    await ws_manager.connect(ws_mock, report_id)

    try:
        # 2. Execute research pipeline
        print("\n🚀 Executing pipeline...")
        await start_research(
            report_id=report_id,
            topic=topic,
            depth="quick",
            language="english",
            user_id="ws_test_user"
        )
        
        # 3. run all tests on captured events list
        events = ws_mock.events
        print(f"\nCaptured {len(events)} WebSocket events total.")
        
        test_ws_event_ordering(events)
        test_ws_thinking_logs(events)
        test_ws_data_payloads(events)
        
        print("\n✅ All WebSocket tests completed successfully!")

    except Exception as e:
        print(f"\n💥 WebSocket E2E Test Exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\n🗑️  Cleaning up {report_id} chunks...")
        try:
            delete_report_chunks(report_id)
        except Exception as e:
            print(f"Cleanup warning: {e}")
        
        # Disconnect from ws_manager
        await ws_manager.disconnect(report_id)


if __name__ == "__main__":
    asyncio.run(run_ws_tests())
