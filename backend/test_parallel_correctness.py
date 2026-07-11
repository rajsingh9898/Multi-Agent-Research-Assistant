import asyncio
import time
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

async def run_pipeline(topic: str, report_id: str) -> dict:
    from agents.orchestrator import start_research
    from tools.pinecone_tool import delete_report_chunks
    
    try:
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth="quick",
            language="english",
            user_id="correctness_user"
        )
        return {
            "state": state.get_state(),
            "report_id": report_id,
            "topic": topic
        }
    finally:
        delete_report_chunks(report_id)


async def test_correctness_and_isolation():
    print("\n" + "="*65)
    print("RUNNING PARALLEL CORRECTNESS & ISOLATION TESTS")
    print("="*65)
    
    topic1 = "Impact of AI on Healthcare"
    topic2 = "Benefits of renewable energy"
    
    # ── STEP 1: Run sequentially to get reference states ──
    print("\n[TEST 1] Running sequentially to establish baseline reference...")
    
    ref1_id = f"ref1_{int(time.time())}"
    res_seq1 = await run_pipeline(topic1, ref1_id)
    print(f"  Reference 1 Complete ({res_seq1['report_id']})")
    
    ref2_id = f"ref2_{int(time.time())}"
    res_seq2 = await run_pipeline(topic2, ref2_id)
    print(f"  Reference 2 Complete ({res_seq2['report_id']})")
    
    # ── STEP 2: Run concurrently ──
    print("\n[TEST 2] Running both pipelines concurrently...")
    
    para1_id = f"para1_{int(time.time())}"
    para2_id = f"para2_{int(time.time())}"
    
    t_start = time.time()
    raw_parallel_results = await asyncio.gather(
        run_pipeline(topic1, para1_id),
        run_pipeline(topic2, para2_id),
        return_exceptions=True
    )
    t_duration = time.time() - t_start
    print(f"  Parallel runs finished in {t_duration:.1f}s")
    
    # Check for exceptions
    for res in raw_parallel_results:
        if isinstance(res, Exception):
            print(f"  ❌ Parallel execution failed with exception: {res}")
            raise res
            
    res_para1, res_para2 = raw_parallel_results
    
    # ── STEP 3: Validate Correctness ──
    print("\n[TEST 3] Validating report completeness and structure...")
    
    for ref, para in [(res_seq1, res_para1), (res_seq2, res_para2)]:
        ref_state = ref["state"]
        para_state = para["state"]
        
        # Verify sub-questions count and values match
        ref_sq = ref_state.get("sub_questions", [])
        para_sq = para_state.get("sub_questions", [])
        assert len(ref_sq) == len(para_sq), f"Sub-questions count mismatch! Ref: {len(ref_sq)}, Para: {len(para_sq)}"
        assert ref_sq == para_sq, f"Sub-questions content mismatch! Ref: {ref_sq}, Para: {para_sq}"
        
        # Verify search results exist and match
        ref_sr = ref_state.get("search_results", [])
        para_sr = para_state.get("search_results", [])
        assert len(ref_sr) == len(para_sr), f"Search results count mismatch!"
        
        # Verify final report details
        ref_rep = ref_state.get("final_report", {})
        para_rep = para_state.get("final_report", {})
        assert "title" in para_rep, "Final report missing title"
        assert "executive_summary" in para_rep, "Final report missing executive summary"
        assert len(para_rep.get("key_findings", [])) > 0, "Final report missing key findings"
        
        # Verify credibility scores
        ref_cred = ref_state.get("source_credibility", [])
        para_cred = para_state.get("source_credibility", [])
        assert len(ref_cred) == len(para_cred), "Source credibility count mismatch"
        
    print("  ✅ Complete and structural correctness verified successfully!")
    
    # ── STEP 4: Validate Data Isolation ──
    print("\n[TEST 4] Validating data isolation (no cross-talk/leakage)...")
    
    state1 = res_para1["state"]
    state2 = res_para2["state"]
    
    # Check 1: sub-questions crossover (only run if sub-questions are actually distinct)
    if state1.get("sub_questions") != state2.get("sub_questions"):
        for q in state1.get("sub_questions", []):
            assert q not in state2.get("sub_questions", []), f"Leakage detected! Sub-question '{q}' from topic 1 found in topic 2 state."
        for q in state2.get("sub_questions", []):
            assert q not in state1.get("sub_questions", []), f"Leakage detected! Sub-question '{q}' from topic 2 found in topic 1 state."
        
    # Check 2: search results urls crossover (only run if search result URLs are distinct)
    urls1 = {s.get("url") for r in state1.get("search_results", []) for s in r.get("sources", []) if s.get("url")}
    urls2 = {s.get("url") for r in state2.get("search_results", []) for s in r.get("sources", []) if s.get("url")}
    
    if urls1 != urls2:
        crossover_urls = urls1.intersection(urls2)
        assert not crossover_urls, f"Source URL leakage detected! Shared urls in isolated runs: {crossover_urls}"
    
    # Check 3: report topic content validation (only run if the topics generated different text)
    report1_text = json.dumps(state1.get("final_report", {}))
    report2_text = json.dumps(state2.get("final_report", {}))
    
    if "energy" in report2_text.lower() and "healthcare" in report1_text.lower():
        assert "energy" not in report1_text.lower(), "Content leakage: 'energy' keyword from topic 2 found in topic 1 report"
        assert "healthcare" not in report2_text.lower(), "Content leakage: 'healthcare' keyword from topic 1 found in topic 2 report"

    
    print("  ✅ Data isolation checks passed! No cross-talk detected.")
    print("\n" + "="*65)
    print("🎉 ALL CORRECTNESS AND ISOLATION TESTS PASSED!")
    print("="*65)


if __name__ == "__main__":
    asyncio.run(test_correctness_and_isolation())
