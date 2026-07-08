import re
import json
import httpx
from urllib.parse import urlparse
from typing import Any, Dict, List
from dataclasses import dataclass, field

@dataclass
class ValidationResult:
    passed: bool
    checks: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: int = 0  # 0-100

    def add_check(self, name: str, passed: bool, detail: str = ""):
        self.checks.append({
            "name": name,
            "passed": passed,
            "detail": detail
        })
        if not passed:
            self.errors.append(f"FAILED: {name} - {detail}")

    def add_warning(self, message: str):
        self.warnings.append(f"WARNING: {message}")

    def calculate_score(self):
        if not self.checks:
            self.score = 0
            self.passed = False
            return
        passed_count = sum(1 for c in self.checks if c["passed"])
        self.score = int((passed_count / len(self.checks)) * 100)
        self.passed = self.score >= 80


def validate_agent_state(state_dict: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult(passed=True)

    # 1. Check sub_questions
    sub_qs = state_dict.get("sub_questions")
    if not isinstance(sub_qs, list):
        result.add_check("sub_questions exists and is list", False, f"Got {type(sub_qs)}")
    else:
        result.add_check("sub_questions exists and is list", True)
        result.add_check("sub_questions length >= 2", len(sub_qs) >= 2, f"Length is {len(sub_qs)}")
        
        all_non_empty_strings = all(isinstance(q, str) and q.strip() != "" for q in sub_qs)
        result.add_check("sub_questions items are non-empty strings", all_non_empty_strings)
        
        no_duplicates = len(sub_qs) == len(set(sub_qs))
        result.add_check("sub_questions has no duplicates", no_duplicates)

    # 2. Check search_results
    search_res = state_dict.get("search_results")
    if not isinstance(search_res, list):
        result.add_check("search_results exists and is list", False, f"Got {type(search_res)}")
    else:
        result.add_check("search_results exists and is list", True)
        result.add_check("search_results length >= 1", len(search_res) >= 1, f"Length is {len(search_res)}")
        
        has_question = all(isinstance(r, dict) and "question" in r for r in search_res)
        result.add_check("search_results items have question key", has_question)
        
        has_sources = all(isinstance(r, dict) and isinstance(r.get("sources"), list) for r in search_res)
        result.add_check("search_results items have sources list", has_sources)
        
        total_sources = sum(len(r.get("sources", [])) for r in search_res if isinstance(r, dict))
        result.add_check("search_results total sources >= 3", total_sources >= 3, f"Total sources: {total_sources}")

    # 3. Check chunk_stats
    chunk_st = state_dict.get("chunk_stats")
    if not isinstance(chunk_st, dict):
        result.add_check("chunk_stats exists and is dict", False, f"Got {type(chunk_st)}")
    else:
        result.add_check("chunk_stats exists and is dict", True)
        total_chunks = chunk_st.get("total_chunks_stored", 0)
        result.add_check("total_chunks_stored > 0", total_chunks > 0, f"Chunks: {total_chunks}")
        
        total_processed = chunk_st.get("total_sources_processed", 0)
        result.add_check("total_sources_processed > 0", total_processed > 0, f"Processed: {total_processed}")
        
        failed = chunk_st.get("failed_sources", 0)
        result.add_check("failed_sources < total_sources_processed", failed < total_processed or total_processed == 0, f"Failed: {failed}, Processed: {total_processed}")

    # 4. Check summaries
    sums = state_dict.get("summaries")
    if not isinstance(sums, list):
        result.add_check("summaries exists and is list", False, f"Got {type(sums)}")
    else:
        result.add_check("summaries exists and is list", True)
        result.add_check("summaries length >= 1", len(sums) >= 1, f"Length is {len(sums)}")
        
        all_have_question = all(isinstance(s, dict) and s.get("question") for s in sums)
        result.add_check("summaries have non-empty question key", all_have_question)
        
        all_have_summary = all(isinstance(s, dict) and isinstance(s.get("summary"), str) and len(s.get("summary", "")) > 50 for s in sums)
        result.add_check("summaries have summary key of length > 50", all_have_summary)
        
        all_have_citations = all(isinstance(s, dict) and isinstance(s.get("citations"), list) for s in sums)
        result.add_check("summaries have citations list key", all_have_citations)

    # 5. Check verified_claims
    claims = state_dict.get("verified_claims")
    if not isinstance(claims, list):
        result.add_check("verified_claims exists and is list", False, f"Got {type(claims)}")
    else:
        result.add_check("verified_claims exists and is list", True)
        result.add_check("verified_claims length >= 1", len(claims) >= 1, f"Length is {len(claims)}")
        
        all_have_claim = all(isinstance(c, dict) and isinstance(c.get("claim"), str) for c in claims)
        result.add_check("verified_claims have claim string key", all_have_claim)
        
        all_have_status = all(isinstance(c, dict) and c.get("status") in ["verified", "uncertain", "unverified"] for c in claims)
        result.add_check("verified_claims have valid status key", all_have_status)
        
        has_verified = any(isinstance(c, dict) and c.get("status") == "verified" for c in claims)
        result.add_check("at least 1 verified claim exists", has_verified)

    # 6. Check final_report
    report = state_dict.get("final_report")
    if not isinstance(report, dict):
        result.add_check("final_report exists and is dict", False, f"Got {type(report)}")
    else:
        result.add_check("final_report exists and is dict", True)
        result.add_check("final_report has title (len > 10)", isinstance(report.get("title"), str) and len(report.get("title", "")) > 10)
        result.add_check("final_report has executive_summary (len > 100)", isinstance(report.get("executive_summary"), str) and len(report.get("executive_summary", "")) > 100)
        result.add_check("final_report has key_findings (list, len >= 3)", isinstance(report.get("key_findings"), list) and len(report.get("key_findings", [])) >= 3)
        result.add_check("final_report has detailed_analysis (len > 300)", isinstance(report.get("detailed_analysis"), str) and len(report.get("detailed_analysis", "")) > 300)
        result.add_check("final_report has limitations (len > 50)", isinstance(report.get("limitations"), str) and len(report.get("limitations", "")) > 50)
        result.add_check("final_report has conclusion (len > 50)", isinstance(report.get("conclusion"), str) and len(report.get("conclusion", "")) > 50)
        result.add_check("final_report has sources (list, len >= 3)", isinstance(report.get("sources"), list) and len(report.get("sources", [])) >= 3)
        result.add_check("final_report has word_count (int > 500)", isinstance(report.get("word_count"), int) and report.get("word_count", 0) > 500)
        
        confidence = report.get("confidence_score", 0)
        result.add_check("final_report has confidence_score 0-100", isinstance(confidence, (int, float)) and 0 <= confidence <= 100)

    # 7. Check followup_questions
    followup = state_dict.get("followup_questions")
    if not isinstance(followup, list):
        result.add_check("followup_questions exists and is list", False, f"Got {type(followup)}")
    else:
        result.add_check("followup_questions exists and is list", True)
        result.add_check("followup_questions length == 5", len(followup) == 5, f"Length: {len(followup)}")
        
        all_have_q = all(isinstance(q, str) and "?" in q for q in followup)
        result.add_check("followup_questions are strings with '?'", all_have_q)
        
        no_dup_followup = len(followup) == len(set(followup))
        result.add_check("followup_questions has no duplicates", no_dup_followup)

    # 8. Check status
    status = state_dict.get("status")
    result.add_check("status equals 'done'", status == "done", f"Got status: {status}")

    # 9. Check confidence_score
    score = state_dict.get("confidence_score")
    result.add_check("confidence_score is integer 0-100", isinstance(score, int) and 0 <= score <= 100, f"Got score: {score}")

    result.calculate_score()
    return result


def validate_report_structure(report: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult(passed=True)

    if not isinstance(report, dict):
        result.add_check("report is dict", False, f"Got {type(report)}")
        result.calculate_score()
        return result
    else:
        result.add_check("report is dict", True)

    # title
    title = report.get("title")
    is_valid_title = isinstance(title, str) and len(title) > 10 and not any(placeholder in title.lower() for placeholder in ["unknown", "placeholder", "tbd"])
    result.add_check("title is string, len > 10, not placeholder", is_valid_title, f"Got: {title}")

    # executive_summary
    exec_sum = report.get("executive_summary")
    if not isinstance(exec_sum, str):
        result.add_check("executive_summary is string", False, f"Got {type(exec_sum)}")
    else:
        result.add_check("executive_summary is string", True)
        words = len(exec_sum.split())
        result.add_check("executive_summary word count > 50", words > 50, f"Word count: {words}")
        result.add_check("executive_summary contains sentences", "." in exec_sum or "।" in exec_sum)

    # key_findings
    findings = report.get("key_findings")
    if not isinstance(findings, list):
        result.add_check("key_findings is list", False, f"Got {type(findings)}")
    else:
        result.add_check("key_findings is list", True)
        result.add_check("key_findings length between 3 and 10", 3 <= len(findings) <= 10, f"Length: {len(findings)}")
        
        all_valid_findings = True
        for f in findings:
            if not isinstance(f, dict):
                all_valid_findings = False
                continue
            point = f.get("point")
            citation = f.get("citation")
            status = f.get("status")
            if not isinstance(point, str) or len(point) <= 20:
                all_valid_findings = False
            if citation is not None and not isinstance(citation, str):
                all_valid_findings = False
            if status is None:
                all_valid_findings = False
        result.add_check("key_findings items are valid dicts with point (len>20), citation (string/empty), and status", all_valid_findings)

    # detailed_analysis
    det_analysis = report.get("detailed_analysis")
    if not isinstance(det_analysis, str):
        result.add_check("detailed_analysis is string", False, f"Got {type(det_analysis)}")
    else:
        result.add_check("detailed_analysis is string", True)
        words = len(det_analysis.split())
        result.add_check("detailed_analysis word count > 150", words > 150, f"Word count: {words}")
        result.add_check("detailed_analysis has multiple paragraphs", "\n" in det_analysis or len(det_analysis) > 500)

    # limitations
    lims = report.get("limitations")
    if not isinstance(lims, str):
        result.add_check("limitations is string", False, f"Got {type(lims)}")
    else:
        result.add_check("limitations is string", True)
        words = len(lims.split())
        result.add_check("limitations word count > 30", words > 30, f"Word count: {words}")

    # conclusion
    conc = report.get("conclusion")
    if not isinstance(conc, str):
        result.add_check("conclusion is string", False, f"Got {type(conc)}")
    else:
        result.add_check("conclusion is string", True)
        words = len(conc.split())
        result.add_check("conclusion word count > 30", words > 30, f"Word count: {words}")

    # sources
    sources = report.get("sources")
    if not isinstance(sources, list):
        result.add_check("sources is list", False, f"Got {type(sources)}")
    else:
        result.add_check("sources is list", True)
        result.add_check("sources length >= 3", len(sources) >= 3, f"Length: {len(sources)}")
        
        all_valid_sources = True
        for s in sources:
            if not isinstance(s, dict):
                all_valid_sources = False
                continue
            if "url" not in s or "title" not in s or "credibility" not in s:
                all_valid_sources = False
        result.add_check("sources items have url, title, and credibility keys", all_valid_sources)

    # word_count
    w_count = report.get("word_count")
    result.add_check("word_count is integer > 500", isinstance(w_count, int) and w_count > 500, f"Got: {w_count}")

    # confidence_score
    c_score = report.get("confidence_score")
    result.add_check("confidence_score is integer 0-100", isinstance(c_score, int) and 0 <= c_score <= 100, f"Got: {c_score}")

    # generated_at
    gen_at = report.get("generated_at")
    result.add_check("generated_at is non-empty string", isinstance(gen_at, str) and gen_at.strip() != "", f"Got: {gen_at}")

    result.calculate_score()
    return result


def validate_citations(report: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult(passed=True)

    findings = report.get("key_findings", [])
    sources = report.get("sources", [])

    citation_urls = []
    
    # Collect from findings
    for f in findings:
        if isinstance(f, dict):
            cite = f.get("citation")
            if isinstance(cite, str) and cite.strip() != "":
                citation_urls.append(cite.strip())

    # Collect from sources
    for s in sources:
        if isinstance(s, dict):
            url = s.get("url")
            if isinstance(url, str) and url.strip() != "":
                citation_urls.append(url.strip())

    if not citation_urls:
        result.add_check("citation URLs collected", False, "No citation URLs found in key_findings or sources")
        result.calculate_score()
        return result
    else:
        result.add_check("citation URLs collected", True)

    # Validate each URL
    for url in citation_urls:
        parsed = urlparse(url)
        
        is_string = isinstance(url, str) and url.strip() != ""
        result.add_check(f"citation '{url}' is string and not empty", is_string)
        
        starts_http = url.startswith("http")
        result.add_check(f"citation '{url}' starts with http", starts_http)
        
        contains_dot = "." in parsed.netloc or "." in url
        result.add_check(f"citation '{url}' contains dot in host", contains_dot)
        
        not_localhost = "localhost" not in url
        result.add_check(f"citation '{url}' does not contain localhost", not_localhost)
        
        not_example = "example.com" not in url
        result.add_check(f"citation '{url}' does not contain example.com", not_example)
        
        not_test = "test" not in parsed.netloc
        result.add_check(f"citation '{url}' does not contain 'test' domain", not_test)
        
        has_netloc = parsed.netloc != ""
        result.add_check(f"citation '{url}' has valid URL structure parsed", has_netloc)

    # Coverage check
    if findings:
        findings_with_citations = sum(
            1 for f in findings
            if isinstance(f, dict) and isinstance(f.get("citation"), str) and f.get("citation", "").startswith("http")
        )
        coverage = findings_with_citations / len(findings)
        result.add_check("citation coverage >= 50%", coverage >= 0.50, f"Coverage: {coverage:.1%}")
    else:
        result.add_check("citation coverage >= 50%", False, "No findings to evaluate coverage")

    # Diversity check
    unique_domains = set()
    for url in citation_urls:
        parsed = urlparse(url)
        if parsed.netloc:
            unique_domains.add(parsed.netloc.replace("www.", ""))
    
    result.add_check("unique domains count >= 2", len(unique_domains) >= 2, f"Domains found: {unique_domains}")

    result.calculate_score()
    return result


def validate_pdf(pdf_url: str) -> ValidationResult:
    result = ValidationResult(passed=True)

    # Check URL format
    is_string = isinstance(pdf_url, str)
    result.add_check("pdf_url is string", is_string)
    if not is_string:
        result.calculate_score()
        return result

    starts_https = pdf_url.startswith("https://") or pdf_url.startswith("http://")
    result.add_check("pdf_url starts with http:// or https://", starts_https)
    
    valid_format = ".pdf" in pdf_url or "storage.googleapis" in pdf_url or "firebase" in pdf_url or "api/export/pdf" in pdf_url or "report" in pdf_url
    result.add_check("pdf_url matches storage format", valid_format)

    # Test accessibility
    try:
        # HEAD request first
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            head_res = client.head(pdf_url)
            
            # If HEAD is 405 (Method Not Allowed) or other failure, fallback to GET
            if head_res.status_code in [405, 403, 401]:
                res = client.get(pdf_url)
            else:
                res = head_res

            # Status code validation (we tolerate 403 since some firewalls block automated scrapers, but let's check for 200 first)
            status_ok = res.status_code == 200
            result.add_check("PDF URL HTTP status 200", status_ok, f"Status code: {res.status_code}")
            
            content_type = res.headers.get("content-type", "")
            is_pdf_content = "pdf" in content_type.lower() or "application/octet-stream" in content_type.lower()
            result.add_check("Content-Type is PDF or octet-stream", is_pdf_content, f"Content-Type: {content_type}")

            # Size check
            content_length = int(res.headers.get("content-length", 0))
            if content_length == 0 and res.status_code == 200 and hasattr(res, "content"):
                content_length = len(res.content)
            
            size_ok = content_length > 10000
            result.add_check("PDF content size > 10KB", size_ok, f"Content size: {content_length} bytes")

    except Exception as e:
        result.add_check("PDF download connection successful", False, f"Exception: {e}")

    result.calculate_score()
    return result


def validate_ws_events(events_list: List[Dict[str, Any]]) -> ValidationResult:
    result = ValidationResult(passed=True)

    if not isinstance(events_list, list):
        result.add_check("events_list is list", False, f"Got {type(events_list)}")
        result.calculate_score()
        return result
    else:
        result.add_check("events_list is list", True)

    # Filter keepalives if any
    events = [e for e in events_list if isinstance(e, dict) and e.get("event") != "keepalive"]

    event_types = [e.get("event") for e in events]

    # connected present
    result.add_check("connected event present", "connected" in event_types)
    
    # research_start present
    result.add_check("research_start event present", "research_start" in event_types)
    
    # report_ready present
    result.add_check("report_ready event present", "report_ready" in event_types)

    # report_ready is last non-keepalive event
    if event_types:
        result.add_check("report_ready is last event", event_types[-1] == "report_ready", f"Last event was: {event_types[-1]}")
    else:
        result.add_check("report_ready is last event", False, "No events found")

    # index of research_start < index of report_ready
    if "research_start" in event_types and "report_ready" in event_types:
        start_idx = event_types.index("research_start")
        ready_idx = event_types.index("report_ready")
        result.add_check("research_start occurs before report_ready", start_idx < ready_idx)
    else:
        result.add_check("research_start occurs before report_ready", False)

    # Check agent coverage
    agents_started = {e.get("agent") for e in events if e.get("event") == "agent_start"}
    agents_done = {e.get("agent") for e in events if e.get("event") == "agent_done"}
    
    expected = {"orchestrator", "search_agent", "summary_agent", "factcheck_agent", "writer_agent", "followup_agent"}
    
    for agent in expected:
        result.add_check(f"{agent} start event present", agent in agents_started)
        result.add_check(f"{agent} done event present", agent in agents_done)

    # Verify agent starts before done for the same agent
    for agent in expected:
        agent_events = [e for e in events if e.get("agent") == agent]
        if len(agent_events) >= 2:
            start_i = next((i for i, e in enumerate(agent_events) if e.get("event") == "agent_start"), -1)
            done_i = next((i for i, e in enumerate(agent_events) if e.get("event") == "agent_done"), -1)
            result.add_check(f"{agent} starts before done", (start_i != -1 and done_i != -1 and start_i < done_i))

    # Event structures validation
    all_struct_valid = True
    for e in events:
        if not isinstance(e, dict):
            all_struct_valid = False
            continue
        if "event" not in e or "agent" not in e or "message" not in e or "timestamp" not in e:
            all_struct_valid = False
        elif not isinstance(e.get("timestamp"), (int, float)):
            all_struct_valid = False
    result.add_check("events have event, agent, message, timestamp fields", all_struct_valid)

    # Thinking logs validation
    thinking_count = sum(1 for e in events if e.get("event") == "thinking_log")
    result.add_check("thinking_log count >= 3", thinking_count >= 3, f"Count: {thinking_count}")
    if thinking_count < 5:
        result.add_warning(f"Thinking logs count is low: {thinking_count}")

    # Check errors
    errors = [e for e in events if e.get("event") == "error"]
    for err in errors:
        result.add_warning(f"Error event: {err.get('message', 'No error message')}")

    result.calculate_score()
    return result


def print_validation_report(result: ValidationResult, label: str):
    print(f"\n{'─'*50}")
    print(f"VALIDATION: {label}")
    print(f"Score: {result.score}/100")
    print(f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}")
    
    if result.errors:
        print("ERRORS:")
        for error in result.errors:
            print(f"  ❌ {error}")
            
    if result.warnings:
        print("WARNINGS:")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")
            
    passed_checks = sum(1 for c in result.checks if c["passed"])
    print(f"Checks: {passed_checks}/{len(result.checks)} passed")
    print(f"{'─'*50}\n")
