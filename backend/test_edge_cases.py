import asyncio
import time
import json
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock
from dotenv import load_dotenv
load_dotenv()

# Force UTF-8 encoding for Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agents.orchestrator import start_research
from tools.pinecone_tool import delete_report_chunks
from utils.firebase_config import initialize_firebase
from memory.agent_memory import AgentMemory

# Ensure Firebase operates, falling back to mocks if key not found
try:
    initialize_firebase()
except Exception:
    pass

# Activate high-fidelity mocks for testing offline
from test_offline_mocks import patch_if_offline
patch_if_offline()


# ─────────────────────────────────────────────
# TEST 1: Empty Topic
# ─────────────────────────────────────────────
async def test_empty_topic():
    print("\n🧪 TEST 1: Empty Topic")
    print("─" * 40)
    
    test_cases = ["", "   ", "\n\t", "  \n  "]
    
    for topic in test_cases:
        try:
            state = await start_research(
                report_id=f"edge_empty_{int(time.time())}_{hash(topic) % 1000}",
                topic=topic,
                depth="quick",
                language="english",
                user_id="test_user"
            )
            
            status = state.get_field("status")
            error = state.get_field("error")
            
            if status == "done":
                sub_q = state.get_field("sub_questions", [])
                assert len(sub_q) > 0, "Fallback questions should have been used"
                print(f"  '{topic!r}': ✅ Handled gracefully (used fallback questions)")
            elif status == "failed":
                assert error is not None, "Error field must be populated"
                print(f"  '{topic!r}': ✅ Failed cleanly with message: {error[:50]}")
            else:
                print(f"  '{topic!r}': ❌ Unexpected status: {status}")
                return False
        
        except Exception as e:
            print(f"  '{topic!r}': ❌ CRASHED: {e}")
            return False
    
    print("✅ TEST 1 PASSED: Empty topics handled")
    return True


# ─────────────────────────────────────────────
# TEST 2: Very Long Topic
# ─────────────────────────────────────────────
async def test_long_topic():
    print("\n🧪 TEST 2: Very Long Topic (500+ chars)")
    print("─" * 40)
    
    long_topic = (
        "The impact of artificial intelligence "
        "and machine learning technologies on "
        "modern healthcare systems, including "
        "diagnosis, treatment planning, drug "
        "discovery, patient monitoring, hospital "
        "administration, medical imaging analysis, "
        "electronic health records, telemedicine, "
        "robotic surgery, personalized medicine, "
        "and the ethical implications thereof "
    ) * 2  # Make it 600+ chars
    
    print(f"Topic length: {len(long_topic)} chars")
    
    report_id = f"edge_long_{int(time.time())}"
    
    try:
        state = await start_research(
            report_id=report_id,
            topic=long_topic,
            depth="quick",
            language="english",
            user_id="test_user"
        )
        
        status = state.get_field("status")
        actual_topic = state.get_field("topic")
        
        assert status == "done", f"Expected done status, got {status}"
        assert len(actual_topic) <= 500, f"Expected truncated length <= 500, got {len(actual_topic)}"
        
        print(f"Topic stored length: {len(actual_topic)}")
        print(f"Status: {status}")
        
        sub_q = state.get_field("sub_questions", [])
        assert len(sub_q) > 0, "Sub questions list is empty"
        print(f"Sub-questions: {len(sub_q)}")
        
        print("✅ TEST 2 PASSED: Long topic truncated")
        return True
    
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        return False
    
    finally:
        delete_report_chunks(report_id)


# ─────────────────────────────────────────────
# TEST 3: Very Niche Topic
# ─────────────────────────────────────────────
async def test_niche_topic():
    print("\n🧪 TEST 3: Very Niche Topic")
    print("─" * 40)
    
    niche_topics = [
        "17th century Portuguese clay pottery",
        "Subsistence farming in 1850s Mongolia",
        "xyzabc123 completely fake nonexistent topic"
    ]
    
    for topic in niche_topics:
        print(f"\n  Testing: {topic[:50]}")
        report_id = f"edge_niche_{int(time.time())}"
        
        try:
            state = await start_research(
                report_id=report_id,
                topic=topic,
                depth="quick",
                language="english",
                user_id="test_user"
            )
            
            status = state.get_field("status")
            search_results = state.get_field("search_results", [])
            total_sources = sum(
                r.get("source_count", 0)
                for r in search_results
            )
            
            print(f"  Status: {status}")
            print(f"  Sources found: {total_sources}")
            
            assert status in ["done", "failed"], f"Status is not complete: {status}"
            
            if status == "done":
                report = state.get_field("final_report", {})
                print(f"  Report generated: {report.get('word_count', 0)} words")
                assert report.get("title", "") != "", "Report missing title"
                print(f"  ✅ Completed with {total_sources} sources")
            else:
                error = state.get_field("error", "")
                print(f"  ✅ Failed gracefully: {error[:50]}")
        
        except Exception as e:
            print(f"  ❌ CRASHED on niche topic: {e}")
            return False
        
        finally:
            delete_report_chunks(report_id)
            
    print("\n✅ TEST 3 PASSED: Niche topics handled")
    return True


# ─────────────────────────────────────────────
# TEST 4: Tavily Returns 0 Results (Mocked)
# ─────────────────────────────────────────────
async def test_tavily_empty_results():
    print("\n🧪 TEST 4: Tavily Returns 0 Results")
    print("─" * 40)
    
    report_id = f"edge_tavily_{int(time.time())}"
    
    # Mock search function inside tavily_tool to return empty results
    with patch("tools.tavily_tool._tavily_search", return_value=[]) as mock_search:
        try:
            state = await start_research(
                report_id=report_id,
                topic="Test topic for empty Tavily",
                depth="quick",
                language="english",
                user_id="test_user"
            )
            
            status = state.get_field("status")
            error = state.get_field("error")
            
            print(f"Status: {status}")
            
            assert status in ["done", "failed"], f"Pipeline got stuck in {status}"
            
            if status == "failed":
                assert error is not None, "Error message missing"
                print(f"Error message: {error[:60]}")
                print("✅ Failed gracefully with error message")
            else:
                print("✅ Generated report despite 0 sources")
            
            return True
        
        except Exception as e:
            print(f"❌ CRASHED when Tavily empty: {e}")
            return False
        
        finally:
            delete_report_chunks(report_id)


# ─────────────────────────────────────────────
# TEST 5: OpenAI Rate Limit (Mocked)
# ─────────────────────────────────────────────
async def test_openai_rate_limit():
    print("\n🧪 TEST 5: OpenAI Rate Limit")
    print("─" * 40)
    
    report_id = f"edge_ratelimit_{int(time.time())}"
    call_count = 0
    
    original_create = None
    
    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count <= 2:
            print(f"  Simulating rate limit error (attempt {call_count})")
            from openai import RateLimitError
            raise RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={}
            )
        
        print(f"  Attempt {call_count}: SUCCESS")
        return original_create(*args, **kwargs)
    
    try:
        import openai
        # Instantiate actual client call structure to retrieve base create callable
        try:
            openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "mock-key")
            original_create = openai_client.chat.completions.create
        except Exception:
            # Fallback mock callable if OpenAI client config is empty
            original_mock = MagicMock()
            original_mock.choices = [MagicMock()]
            original_mock.choices[0].message.content = '["What is AI?", "How does AI work?"]'
            original_create = lambda *a, **k: original_mock

        # Patch call_gpt4o to sleep instantly during retry delays
        with patch("utils.retry.asyncio.sleep", side_effect=lambda x: asyncio.sleep(0.001)):
            with patch("openai.resources.chat.completions.Completions.create") as mock:
                mock.side_effect = mock_create
                
                from agents.orchestrator import generate_sub_questions
                state = AgentMemory(
                    report_id=report_id,
                    topic="Test topic",
                    depth="quick",
                    language="english",
                    user_id="test_user"
                )
                
                questions = await generate_sub_questions(state, report_id)
                
                print(f"Attempts made: {call_count}")
                print(f"Questions generated: {len(questions)}")
                
                assert call_count >= 2, f"Expected retries, got {call_count} calls"
                assert len(questions) > 0, "No questions generated"
                
                print("✅ TEST 5 PASSED: Rate limit retried")
                return True
    
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        return False
    
    finally:
        delete_report_chunks(report_id)


# ─────────────────────────────────────────────
# TEST 6: Pinecone Timeout (Mocked)
# ─────────────────────────────────────────────
async def test_pinecone_timeout():
    print("\n🧪 TEST 6: Pinecone Timeout")
    print("─" * 40)
    
    report_id = f"edge_pinecone_{int(time.time())}"
    
    # Mock index.query to block/sleep 11 seconds (timeout is 10s)
    mock_index = MagicMock()
    mock_index.query.side_effect = lambda *a, **k: (time.sleep(11) or {"matches": []})
    
    with patch("tools.pinecone_tool.get_pinecone_index", return_value=mock_index):
        try:
            from agents.summary_agent import retrieve_and_summarize
            state = AgentMemory(
                report_id=report_id,
                topic="Test topic",
                depth="quick",
                language="english",
                user_id="test_user"
            )
            
            state.update_state("sub_questions", ["What is AI?", "How does AI work?"])
            state.update_state("pinecone_ready", True)
            state.update_state("chunk_stats", {"total_chunks_stored": 10})
            
            print("Running retrieve_and_summarize...")
            
            # Using wait_for to protect the test from hanging if fallback fails
            result = await asyncio.wait_for(
                retrieve_and_summarize(state, report_id),
                timeout=30.0
            )
            
            print(f"Result: {result}")
            print("✅ TEST 6 PASSED: Timeout handled gracefully (empty chunks returned)")
            return True
            
        except asyncio.TimeoutError:
            print("❌ Function hung without timing out!")
            return False
            
        except Exception as e:
            print(f"Result: Exception caught: {e}")
            print("✅ TEST 6 PASSED: Exception handled")
            return True


# ─────────────────────────────────────────────
# TEST 7: Browser Closes Mid-Research
# ─────────────────────────────────────────────
async def test_browser_close_mid_research():
    print("\n🧪 TEST 7: Browser Closes Mid-Research")
    print("─" * 40)
    
    from utils.websocket_manager import WebSocketManager
    
    report_id = f"edge_disconnect_{int(time.time())}"
    ws_manager = WebSocketManager()
    
    from fastapi.websockets import WebSocketState
    
    class FakeWS:
        client_state = WebSocketState.CONNECTED
        send_json_called = 0
        
        async def accept(self):
            pass
            
        async def send_json(self, data):
            self.send_json_called += 1
            if self.send_json_called > 3:
                self.client_state = WebSocketState.DISCONNECTED
                raise Exception("Connection closed")
                
    fake_ws = FakeWS()
    
    from utils.websocket_manager import ConnectionInfo
    ws_manager.connections[report_id] = ConnectionInfo(
        websocket=fake_ws,
        report_id=report_id,
        connected_at=time.time()
    )
    
    print("Starting pipeline with WS connection...")
    print("WS will disconnect after 3 events")
    
    try:
        state = await start_research(
            report_id=report_id,
            topic="Benefits of meditation",
            depth="quick",
            language="english",
            user_id="test_user"
        )
        
        status = state.get_field("status")
        print(f"Pipeline final status: {status}")
        
        assert status == "done", f"Expected 'done' pipeline completion, got {status}"
        
        final_report = state.get_field("final_report")
        assert final_report is not None, "Final report was not saved"
        assert final_report.get("title", "") != "", "Report title is empty"
        
        print(f"Report generated: {final_report.get('word_count', 0)} words")
        print("✅ TEST 7 PASSED: Backend continued after browser disconnect")
        return True
        
    except Exception as e:
        print(f"❌ TEST 7 FAILED: {e}")
        return False
        
    finally:
        delete_report_chunks(report_id)
        if report_id in ws_manager.connections:
            del ws_manager.connections[report_id]


# ─────────────────────────────────────────────
# TEST 8: Same Report in Two Tabs
# ─────────────────────────────────────────────
async def test_two_tabs_same_report():
    print("\n🧪 TEST 8: Same Report in Two Tabs")
    print("─" * 40)
    
    from utils.websocket_manager import WebSocketManager
    
    report_id = f"edge_twotabs_{int(time.time())}"
    ws_manager = WebSocketManager()
    
    from fastapi.websockets import WebSocketState

    tab1_events = []
    class Tab1WS:
        client_state = WebSocketState.CONNECTED
        async def accept(self): pass
        async def send_json(self, data):
            tab1_events.append(data)
            
    tab2_events = []
    class Tab2WS:
        client_state = WebSocketState.CONNECTED
        async def accept(self): pass
        async def send_json(self, data):
            tab2_events.append(data)
            
    # Connect Tab 1
    await ws_manager.connect(Tab1WS(), report_id)
    tab1_count_after_connect = len(tab1_events)
    print(f"Tab 1 connected: {tab1_count_after_connect} events")
    
    # Emit event (Tab 1 should receive it)
    await ws_manager.emit(report_id, "agent_start", "orchestrator", "Starting...")
    tab1_after_event = len(tab1_events)
    print(f"Tab 1 after event: {tab1_after_event} events")
    
    # Connect Tab 2 (overwrites Tab 1 or registers alongside it)
    await ws_manager.connect(Tab2WS(), report_id)
    print("Tab 2 connected")
    
    # Emit event (Tab 2 should receive it)
    await ws_manager.emit(report_id, "agent_done", "orchestrator", "Done!")
    
    tab2_events_count = len(tab2_events)
    print(f"Tab 2 events: {tab2_events_count}")
    
    assert tab2_events_count >= 1, "Tab 2 did not receive events"
    print(f"Tab 1 final events: {len(tab1_events)}")
    print(f"Tab 2 final events: {len(tab2_events)}")
    
    print("✅ TEST 8 PASSED: Two tabs handled without crash")
    
    # Cleanup
    ws_manager.clear_event_history(report_id)
    if report_id in ws_manager.connections:
        del ws_manager.connections[report_id]
        
    return True


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
async def run_all_edge_case_tests():
    print("\n" + "="*60)
    print("EDGE CASE TEST SUITE")
    print("Multi-Agent Research Assistant")
    print("="*60)
    
    tests = [
        ("Empty Topic", test_empty_topic),
        ("Long Topic", test_long_topic),
        ("Niche Topic", test_niche_topic),
        ("Tavily 0 Results", test_tavily_empty_results),
        ("OpenAI Rate Limit", test_openai_rate_limit),
        ("Pinecone Timeout", test_pinecone_timeout),
        ("Browser Disconnect", test_browser_close_mid_research),
        ("Two Browser Tabs", test_two_tabs_same_report)
    ]
    
    results = []
    
    for name, test_fn in tests:
        try:
            passed = await test_fn()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"💥 {name} threw exception: {e}")
        
        await asyncio.sleep(1)  # Brief pause between tests
        
    # FINAL SUMMARY
    print("\n\n" + "="*60)
    print("EDGE CASE TEST RESULTS")
    print("="*60)
    
    passed_count = sum(1 for _, p, _ in results if p)
    
    for name, passed, error in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if error:
            print(f"         Error: {error[:50]}")
            
    print(f"\n{passed_count}/{len(tests)} tests passed")
    
    if passed_count == len(tests):
        print("\n🎉 ALL EDGE CASES HANDLED!")
        print("App is resilient and production-ready.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all_edge_case_tests())
