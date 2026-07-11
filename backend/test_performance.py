import asyncio
import time
import json
import statistics
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Any
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

@dataclass
class AgentTiming:
    agent_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    sub_timings: Dict[str, float] = field(default_factory=dict)
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
    
    def add_sub_timing(self, name: str, duration: float):
        self.sub_timings[name] = duration


@dataclass
class PipelineProfile:
    topic: str
    depth: str
    total_duration: float = 0.0
    agent_timings: List[AgentTiming] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def add_agent(self, timing: AgentTiming):
        self.agent_timings.append(timing)
    
    def get_slowest_agent(self) -> AgentTiming:
        return max(
            self.agent_timings,
            key=lambda x: x.duration
        )
    
    def print_report(self):
        print("\n" + "="*60)
        print("PERFORMANCE PROFILE")
        print(f"Topic: {self.topic[:50]}")
        print(f"Total time: {self.total_duration:.1f}s")
        print("="*60)
        
        print("\nAGENT BREAKDOWN:")
        print(f"{'Agent':<20} {'Time':>8} {'%':>6}")
        print("─"*36)
        
        for timing in sorted(
            self.agent_timings,
            key=lambda x: x.duration,
            reverse=True
        ):
            pct = (timing.duration / self.total_duration * 100) if self.total_duration > 0 else 0
            bar = "█" * int(pct / 5)
            print(
                f"{timing.agent_name:<20} "
                f"{timing.duration:>7.1f}s "
                f"{pct:>5.1f}% {bar}"
            )
        
        print("\nSUB-TIMINGS:")
        for timing in self.agent_timings:
            if timing.sub_timings:
                print(f"\n  {timing.agent_name}:")
                for name, dur in timing.sub_timings.items():
                    print(f"    {name}: {dur:.2f}s")
        
        print(f"\nMETADATA:")
        for k, v in self.metadata.items():
            print(f"  {k}: {v}")
        
        if self.agent_timings:
            slowest = self.get_slowest_agent()
            print(f"\n⚠️  BOTTLENECK: {slowest.agent_name} ({slowest.duration:.1f}s)")
        print("="*60)


async def profile_pipeline(topic: str, depth: str = "quick") -> PipelineProfile:
    profile = PipelineProfile(topic=topic, depth=depth)
    events_log = []
    
    from utils.websocket_manager import ws_manager, ConnectionInfo
    
    report_id = f"perf_{int(time.time())}"
    
    from fastapi.websockets import WebSocketState
    
    class TimingWS:
        client_state = WebSocketState.CONNECTED
        
        async def accept(self):
            pass
            
        async def send_json(self, data):
            events_log.append({
                **data,
                "received_at": time.time()
            })

            
    # Inject timing WS to capture real-time events & timings
    ws_manager.connections[report_id] = ConnectionInfo(
        websocket=TimingWS(),
        report_id=report_id,
        connected_at=time.time()
    )

    
    total_start = time.time()
    
    from agents.orchestrator import start_research
    state = await start_research(
        report_id=report_id,
        topic=topic,
        depth=depth,
        language="english",
        user_id="perf_test_user"
    )
    
    total_end = time.time()
    profile.total_duration = total_end - total_start
    
    # Process event timings
    agent_starts = {}
    agent_ends = {}
    
    for event in events_log:
        agent = event.get("agent", "")
        evt_type = event.get("event", "")
        evt_time = event.get("received_at", 0)
        
        if evt_type == "agent_start":
            agent_starts[agent] = evt_time
        elif evt_type == "agent_done":
            agent_ends[agent] = evt_time
            
    # Create AgentTiming for each agent
    agents = [
        "orchestrator", "search_agent",
        "summary_agent", "factcheck_agent",
        "writer_agent", "followup_agent"
    ]
    
    for agent in agents:
        if agent in agent_starts and agent in agent_ends:
            timing = AgentTiming(agent_name=agent)
            timing.start_time = agent_starts[agent]
            timing.end_time = agent_ends[agent]
            timing.duration = timing.end_time - timing.start_time
            profile.add_agent(timing)
            
    # Add metadata from state
    search_results = state.get_field("search_results", [])
    total_sources = sum(
        r.get("source_count", 0)
        for r in search_results
    )
    chunk_stats = state.get_field("chunk_stats", {})
    
    profile.metadata = {
        "sub_questions": len(state.get_field("sub_questions", [])),
        "total_sources": total_sources,
        "chunks_stored": chunk_stats.get("total_chunks_stored", 0),
        "summaries": len(state.get_field("summaries", [])),
        "verified_claims": len(state.get_field("verified_claims", [])),
        "word_count": state.get_field("final_report", {}).get("word_count", 0),
        "confidence_score": state.get_field("confidence_score", 0)
    }
    
    # Cleanup
    from tools.pinecone_tool import delete_report_chunks
    delete_report_chunks(report_id)
    
    if report_id in ws_manager.connections:
        del ws_manager.connections[report_id]
        
    return profile


async def run_benchmark(topic: str, runs: int = 3, depth: str = "quick") -> dict:
    print(f"\n📊 BENCHMARK: {topic[:40]}")
    print(f"Running {runs} times with depth={depth}...")
    
    profiles = []
    for i in range(runs):
        print(f"\nRun {i+1}/{runs}...")
        profile = await profile_pipeline(topic, depth)
        profiles.append(profile)
        print(f"  Time: {profile.total_duration:.1f}s")
        
        if i < runs - 1:
            await asyncio.sleep(5)  # Brief pause
            
    durations = [p.total_duration for p in profiles]
    
    return {
        "topic": topic,
        "runs": runs,
        "min": min(durations),
        "max": max(durations),
        "mean": statistics.mean(durations),
        "median": statistics.median(durations),
        "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
        "profiles": profiles
    }


async def measure_baseline():
    print("\n" + "="*60)
    print("PERFORMANCE BASELINE MEASUREMENT")
    print("="*60)
    
    topic = "Impact of AI on Healthcare"
    
    print("\n⏱️  Running single profile...")
    profile = await profile_pipeline(topic, "quick")
    profile.print_report()
    
    if profile.total_duration < 60:
        print(f"\n✅ ALREADY UNDER TARGET: {profile.total_duration:.1f}s < 60s")
    else:
        print(f"\n❌ OVER TARGET: {profile.total_duration:.1f}s > 60s")
        print("Optimization needed!")
        
        if profile.agent_timings:
            slowest = profile.get_slowest_agent()
            print(f"OPTIMIZE FIRST: {slowest.agent_name}")
            
    return profile


if __name__ == "__main__":
    asyncio.run(measure_baseline())
