import asyncio
import time
import statistics
import json
import sys
from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 encoding for Windows stdout/stderr
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

# Activate high-fidelity mocks for testing offline
from test_offline_mocks import patch_if_offline
patch_if_offline()

async def time_single_run(topic: str, depth: str = "quick") -> dict:
    from agents.orchestrator import start_research
    from tools.pinecone_tool import delete_report_chunks
    from utils.websocket_manager import ws_manager, ConnectionInfo
    from fastapi.websockets import WebSocketState
    
    report_id = f"bench_{int(time.time())}"
    agent_times = {}
    events = []
    
    class RecordingWS:
        client_state = WebSocketState.CONNECTED
        async def accept(self):
            pass
        async def send_json(self, data):
            events.append({
                **data,
                "t": time.time()
            })
            
    ws_manager.connections[report_id] = ConnectionInfo(
        websocket=RecordingWS(),
        report_id=report_id,
        connected_at=time.time()
    )
    
    try:
        start = time.time()
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language="english",
            user_id="bench_user"
        )
        total = time.time() - start
        
        # Calculate agent times from events
        starts = {
            e["agent"]: e["t"]
            for e in events
            if e.get("event") == "agent_start"
        }
        ends = {
            e["agent"]: e["t"]
            for e in events
            if e.get("event") == "agent_done"
        }
        
        for agent in starts:
            if agent in ends:
                agent_times[agent] = ends[agent] - starts[agent]
                
        return {
            "total": total,
            "agent_times": agent_times,
            "events_count": len(events),
            "word_count": state.get_field("final_report", {}).get("word_count", 0),
            "status": state.get_field("status")
        }
        
    finally:
        delete_report_chunks(report_id)
        if report_id in ws_manager.connections:
            del ws_manager.connections[report_id]


async def run_benchmark_suite():
    print("\n" + "="*65)
    print("PERFORMANCE BENCHMARK SUITE")
    print("="*65)
    
    TEST_TOPICS = [
        "Impact of AI on Healthcare",
        "Benefits of renewable energy",
        "Future of quantum computing"
    ]
    
    all_results = []
    
    for topic in TEST_TOPICS:
        print(f"\n\n📊 Benchmarking: {topic[:40]}")
        print("Running 2 times...")
        
        topic_results = []
        for run in range(2):
            print(f"  Run {run+1}/2...", end="", flush=True)
            result = await time_single_run(topic, "quick")
            topic_results.append(result)
            print(f" {result['total']:.1f}s")
            await asyncio.sleep(5)
            
        avg_time = statistics.mean([r["total"] for r in topic_results])
        all_results.extend(topic_results)
        
        # Show agent breakdown for first run
        print("\n  Agent timing breakdown:")
        first = topic_results[0]
        if first["agent_times"]:
            for agent, t in sorted(
                first["agent_times"].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                bar = "█" * int(t/2)
                print(f"    {agent:<20} {t:5.1f}s {bar}")
                
        print(f"\n  Average: {avg_time:.1f}s")
        
        if avg_time < 60:
            print("  ✅ UNDER TARGET (60s)")
        else:
            print(f"  ❌ OVER TARGET by {avg_time-60:.1f}s")
            
    # OVERALL SUMMARY
    all_times = [r["total"] for r in all_results]
    
    print("\n\n" + "="*65)
    print("BENCHMARK SUMMARY")
    print("="*65)
    print(f"Total runs: {len(all_times)}")
    print(f"Min time: {min(all_times):.1f}s")
    print(f"Max time: {max(all_times):.1f}s")
    print(f"Average:  {statistics.mean(all_times):.1f}s")
    print(f"Median:   {statistics.median(all_times):.1f}s")
    
    target = 60.0
    under_target = sum(1 for t in all_times if t < target)
    print(f"\nUnder {target}s: {under_target}/{len(all_times)} runs ({under_target/len(all_times)*100:.0f}%)")
    
    if statistics.mean(all_times) < target:
        print("\n🎉 TARGET ACHIEVED!")
        print(f"Average {statistics.mean(all_times):.1f}s < {target}s")
    else:
        over = statistics.mean(all_times) - target
        print(f"\n⚠️  Still {over:.1f}s over target")
        print("Additional optimization needed")
    print("="*65)


if __name__ == "__main__":
    asyncio.run(run_benchmark_suite())
