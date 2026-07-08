import asyncio
import sys
import time
from typing import Any, Dict, List
from dotenv import load_dotenv

# Setup paths
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

from utils.firebase_config import initialize_firebase, get_firestore
from agents.orchestrator import start_research
from tools.pinecone_tool import delete_report_chunks, get_index_stats
from tools.pdf_export import generate_and_upload_pdf

from test_offline_mocks import patch_if_offline
patch_if_offline()
initialize_firebase()

async def test_empty_topic() -> bool:
    """BUG TEST 1: Empty topic handling."""
    report_id = f"bug_test_empty_{int(time.time())}"
    try:
        state = await start_research(
            report_id=report_id,
            topic="",
            depth="quick",
            language="english",
            user_id="bug_test_user"
        )
        status = state.get_field("status")
        # Should complete gracefully as done or failed, without unhandled exceptions
        return status in ["done", "failed"]
    except Exception as e:
        print(f"    ❌ Empty topic failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_long_topic() -> bool:
    """BUG TEST 2: Very long topic."""
    report_id = f"bug_test_long_{int(time.time())}"
    long_topic = "a " * 250  # 500 characters
    try:
        state = await start_research(
            report_id=report_id,
            topic=long_topic,
            depth="quick",
            language="english",
            user_id="bug_test_user"
        )
        status = state.get_field("status")
        return status == "done"
    except Exception as e:
        print(f"    ❌ Long topic failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_special_chars() -> bool:
    """BUG TEST 3: Special characters in topic."""
    report_id = f"bug_test_special_{int(time.time())}"
    special_topic = "AI & ML: What's next? (2025)"
    try:
        state = await start_research(
            report_id=report_id,
            topic=special_topic,
            depth="quick",
            language="english",
            user_id="bug_test_user"
        )
        status = state.get_field("status")
        sub_qs = state.get_field("sub_questions", [])
        return status == "done" and len(sub_qs) >= 2
    except Exception as e:
        print(f"    ❌ Special characters failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_hindi() -> bool:
    """BUG TEST 4: Hindi language report."""
    report_id = f"bug_test_hindi_{int(time.time())}"
    topic = "भारत में AI का भविष्य"
    try:
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth="quick",
            language="hindi",
            user_id="bug_test_user"
        )
        final_report = state.get_field("final_report", {})
        title = final_report.get("title", "")
        
        # Check that report is done, has unicode content, and PDF generates successfully
        pdf_res = generate_and_upload_pdf(
            report=final_report,
            topic=topic,
            report_id=report_id
        )
        
        status = state.get_field("status")
        pdf_ok = pdf_res.get("success") is True
        
        return status == "done" and pdf_ok
    except Exception as e:
        print(f"    ❌ Hindi test failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_expert_depth() -> bool:
    """BUG TEST 5: Expert depth."""
    report_id = f"bug_test_expert_{int(time.time())}"
    topic = "quantum computing basics"
    try:
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth="expert",
            language="english",
            user_id="bug_test_user"
        )
        status = state.get_field("status")
        sub_qs = state.get_field("sub_questions", [])
        
        # Expert depth expects exactly 6 sub-questions
        is_expert_count = len(sub_qs) == 6
        return status == "done" and is_expert_count
    except Exception as e:
        print(f"    ❌ Expert depth failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_duplicate_id() -> bool:
    """BUG TEST 6: Duplicate report_id."""
    report_id = f"bug_test_dup_{int(time.time())}"
    topic_1 = "Electric vehicles battery tech"
    topic_2 = "Electric vehicles autonomous driving"
    try:
        # Run first research pipeline
        state_1 = await start_research(
            report_id=report_id,
            topic=topic_1,
            depth="quick",
            language="english",
            user_id="bug_test_user"
        )
        
        # Run second research pipeline using same report_id
        state_2 = await start_research(
            report_id=report_id,
            topic=topic_2,
            depth="quick",
            language="english",
            user_id="bug_test_user"
        )
        
        db = get_firestore()
        doc = db.collection("reports").document(report_id).get()
        
        if doc.exists:
            data = doc.to_dict()
            saved_topic = data.get("topic", "")
            # Verify Firestore overwritten correctly
            overwritten = saved_topic == topic_2
            return state_2.get_field("status") == "done" and overwritten
        return False
    except Exception as e:
        print(f"    ❌ Duplicate report_id test failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id)


async def test_concurrent() -> bool:
    """BUG TEST 7: Concurrent pipelines."""
    report_id_1 = f"bug_test_concurrent_1_{int(time.time())}"
    report_id_2 = f"bug_test_concurrent_2_{int(time.time())}"
    try:
        # Launch concurrently
        results = await asyncio.gather(
            start_research(
                report_id=report_id_1,
                topic="Quantum physics",
                depth="quick",
                language="english",
                user_id="bug_test_user"
            ),
            start_research(
                report_id=report_id_2,
                topic="Molecular biology",
                depth="quick",
                language="english",
                user_id="bug_test_user"
            ),
            return_exceptions=True
        )
        
        ok_1 = False
        ok_2 = False
        
        if not isinstance(results[0], Exception):
            ok_1 = results[0].get_field("status") == "done"
            
        if not isinstance(results[1], Exception):
            ok_2 = results[1].get_field("status") == "done"
            
        return ok_1 and ok_2
    except Exception as e:
        print(f"    ❌ Concurrent pipelines failed with exception: {e}")
        return False
    finally:
        delete_report_chunks(report_id_1)
        delete_report_chunks(report_id_2)


async def run_bug_tests():
    print("=" * 65)
    print("Automated Edge Case and Bug Detection Test Suite")
    print("=" * 65)

    bug_tests = [
        ("Empty topic", test_empty_topic),
        ("Long topic", test_long_topic),
        ("Special chars", test_special_chars),
        ("Hindi language", test_hindi),
        ("Expert depth", test_expert_depth),
        ("Duplicate ID", test_duplicate_id),
        ("Concurrent", test_concurrent)
    ]

    results = []
    for name, test_fn in bug_tests:
        print(f"\n🔍 Testing: {name}...")
        try:
            passed = await test_fn()
            results.append((name, passed, None))
            print(f"  {'✅' if passed else '❌'} {name}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  💥 {name} failed with unhandled exception: {e}")

    passed_count = sum(1 for _, p, _ in results if p)
    print("\n" + "=" * 65)
    print(f"BUG TEST RESULTS SUMMARY: {passed_count}/{len(bug_tests)} PASSED")
    print("=" * 65)
    
    for name, passed, err in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        err_msg = f" (Error: {err})" if err else ""
        print(f"  {name:<30} {status}{err_msg}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_bug_tests())
