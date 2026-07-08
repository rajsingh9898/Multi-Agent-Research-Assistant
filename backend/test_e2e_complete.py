import asyncio
import sys
import time
import json
import os
from dataclasses import dataclass
from dotenv import load_dotenv

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
load_dotenv()

from agents.orchestrator import start_research
from tools.pinecone_tool import delete_report_chunks, get_index_stats
from utils.firebase_config import initialize_firebase, get_firestore
from tools.pdf_export import generate_and_upload_pdf
from test_report_validator import (
    validate_agent_state,
    validate_report_structure,
    validate_citations,
    validate_pdf,
    print_validation_report,
    ValidationResult
)

from test_offline_mocks import patch_if_offline
patch_if_offline()
initialize_firebase()

@dataclass
class TopicTestResult:
    topic: str
    report_id: str
    duration_seconds: float
    passed: bool
    pipeline_score: int
    report_score: int
    citation_score: int
    pdf_score: int
    confidence_score: int
    word_count: int
    total_sources: int
    total_claims: int
    error: str | None = None


async def run_single_topic_test(topic: str, depth: str = "quick") -> TopicTestResult:
    report_id = f"e2e_test_{topic[:20].replace(' ', '_').replace(':', '').replace('&', '').replace('(', '').replace(')', '').lower()}_{int(time.time())}"
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"TESTING: {topic}")
    print(f"Report ID: {report_id}")
    print(f"{'='*60}")

    try:
        # 1. Run pipeline
        print("🚀 Starting pipeline...")
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language="english",
            user_id="e2e_test_user"
        )
        
        duration = time.time() - start_time
        print(f"⏱️  Pipeline completed in {duration:.1f}s")

        # 2. Validate agent state
        print("\n📊 Validating agent state...")
        state_dict = state.get_state()
        pipeline_result = validate_agent_state(state_dict)
        print_validation_report(pipeline_result, "Pipeline State")

        # 3. Validate report structure
        print("\n📄 Validating report structure...")
        final_report = state.get_field("final_report", {})
        report_result = validate_report_structure(final_report)
        print_validation_report(report_result, "Report Structure")

        # 4. Validate citations
        print("\n🔗 Validating citations...")
        citation_result = validate_citations(final_report)
        print_validation_report(citation_result, "Citations")

        # 5. Generate and validate PDF
        print("\n📥 Testing PDF export...")
        pdf_result_data = generate_and_upload_pdf(
            report=final_report,
            topic=topic,
            report_id=report_id
        )

        if pdf_result_data.get("success"):
            pdf_url = pdf_result_data.get("pdf_url")
            print(f"PDF URL: {pdf_url[:60]}...")
            pdf_result = validate_pdf(pdf_url)
            print_validation_report(pdf_result, "PDF Export")
        else:
            pdf_result = ValidationResult(passed=False)
            pdf_result.errors.append("PDF generation failed")
            print("❌ PDF generation failed")

        # 6. Verify Firestore sync
        print("\n🔥 Verifying Firestore sync...")
        db = get_firestore()
        doc = db.collection("reports").document(report_id).get()

        if doc.exists:
            data = doc.to_dict()
            fs_status = data.get("status", "")
            fs_confidence = data.get("confidenceScore", 0)
            print(f"Firestore status: {fs_status}")
            print(f"Firestore confidence: {fs_confidence}%")
            if fs_status != "done":
                print(f"⚠️  Expected 'done', got '{fs_status}'")
        else:
            print("⚠️  Report not found in Firestore")

        # Collect statistics
        search_results = state.get_field("search_results", [])
        total_sources = sum(len(r.get("sources", [])) for r in search_results if isinstance(r, dict))
        verified_claims = state.get_field("verified_claims", [])

        overall_passed = all([
            pipeline_result.passed,
            report_result.passed,
            citation_result.score >= 60
        ])

        result = TopicTestResult(
            topic=topic,
            report_id=report_id,
            duration_seconds=duration,
            passed=overall_passed,
            pipeline_score=pipeline_result.score,
            report_score=report_result.score,
            citation_score=citation_result.score,
            pdf_score=pdf_result.score if pdf_result_data.get("success") else 0,
            confidence_score=state.get_field("confidence_score", 0),
            word_count=final_report.get("word_count", 0),
            total_sources=total_sources,
            total_claims=len(verified_claims)
        )

        # Print summary
        print(f"\n{'─'*60}")
        status = "✅ PASSED" if overall_passed else "❌ FAILED"
        print(f"RESULT: {status}")
        print(f"Time: {duration:.1f}s")
        print(f"Confidence: {result.confidence_score}%")
        print(f"Words: {result.word_count}")
        print(f"Sources: {total_sources}")
        print(f"Claims: {len(verified_claims)}")
        print(f"Pipeline: {pipeline_result.score}/100")
        print(f"Report: {report_result.score}/100")
        print(f"Citations: {citation_result.score}/100")

        return result

    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

        return TopicTestResult(
            topic=topic,
            report_id=report_id,
            duration_seconds=duration,
            passed=False,
            pipeline_score=0,
            report_score=0,
            citation_score=0,
            pdf_score=0,
            confidence_score=0,
            word_count=0,
            total_sources=0,
            total_claims=0,
            error=str(e)
        )

    finally:
        # 7. Cleanup
        print(f"\n🗑️  Cleaning up {report_id}...")
        try:
            delete_report_chunks(report_id)
        except Exception as e:
            print(f"Cleanup warning: {e}")


async def run_all_e2e_tests():
    TOPICS = [
        "Impact of AI on Healthcare",
        "Climate change solutions 2025",
        "Future of electric vehicles",
        "Blockchain in finance",
        "Space exploration 2025"
    ]

    print("\n" + "="*70)
    print("MULTI-AGENT RESEARCH ASSISTANT")
    print("END-TO-END INTEGRATION TESTS")
    print(f"Testing {len(TOPICS)} topics")
    print("="*70)

    # Check Pinecone before starting
    stats_before = get_index_stats()
    print(f"\n📊 Pinecone vectors before: {stats_before.get('total_vectors', 0)}")

    # Run all tests
    results = []
    total_start = time.time()

    for i, topic in enumerate(TOPICS, 1):
        print(f"\n\n{'#'*70}")
        print(f"TEST {i}/{len(TOPICS)}")
        print(f"{'#'*70}")

        result = await run_single_topic_test(topic=topic, depth="quick")
        results.append(result)

        # Brief pause between tests
        if i < len(TOPICS):
            print(f"\n⏸️  Pausing 5 seconds before next test...")
            await asyncio.sleep(5)

    total_time = time.time() - total_start

    # Final report
    print("\n\n" + "="*70)
    print("FINAL TEST RESULTS")
    print("="*70)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print(f"\n📊 OVERALL: {passed}/{len(results)} PASSED")
    print(f"⏱️  Total time: {total_time/60:.1f} minutes")
    print(f"\n{'─'*70}")
    print(f"{'Topic':<35} {'Status':<10} {'Time':>6} {'Conf':>5} {'Words':>6}")
    print(f"{'─'*70}")

    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(
            f"{r.topic[:34]:<35} "
            f"{status:<10} "
            f"{r.duration_seconds:>5.0f}s "
            f"{r.confidence_score:>4}% "
            f"{r.word_count:>6}"
        )

    print(f"{'─'*70}")

    # Averages
    done_results = [r for r in results if r.passed]
    if done_results:
        avg_conf = sum(r.confidence_score for r in done_results) / len(done_results)
        avg_words = sum(r.word_count for r in done_results) / len(done_results)
        avg_time = sum(r.duration_seconds for r in done_results) / len(done_results)

        print("\nAverages (passed tests):")
        print(f"  Confidence: {avg_conf:.0f}%")
        print(f"  Words/report: {avg_words:.0f}")
        print(f"  Time/report: {avg_time:.0f}s")

    # Score breakdown
    print("\n📈 SCORE BREAKDOWN:")
    print(f"{'Topic':<35} {'Pipeline':>9} {'Report':>7} {'Cite':>5} {'PDF':>4}")
    for r in results:
        print(
            f"{r.topic[:34]:<35} "
            f"{r.pipeline_score:>8}/100 "
            f"{r.report_score:>6}/100 "
            f"{r.citation_score:>4}/100 "
            f"{r.pdf_score:>3}/100"
        )

    # Failed tests details
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        print("\n❌ FAILED TESTS DETAILS:")
        for r in failed_results:
            print(f"\n  Topic: {r.topic}")
            if r.error:
                print(f"  Error: {r.error}")

    # Final status
    print("\n" + "="*70)
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("Your pipeline is production ready.")
    elif failed <= 1:
        print(f"⚠️  {failed} test failed.")
        print("Review errors above and fix.")
    else:
        print(f"❌ {failed} tests failed.")
        print("Significant issues need fixing.")
    print("="*70)

    # Check Pinecone after
    stats_after = get_index_stats()
    print(f"\n📊 Pinecone vectors after: {stats_after.get('total_vectors', 0)}")
    print("(Should be same or close to before)")

    return results


if __name__ == "__main__":
    asyncio.run(run_all_e2e_tests())
