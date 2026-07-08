import asyncio
import httpx
import re
import sys
import time
from urllib.parse import urlparse
from collections import Counter
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

from test_offline_mocks import patch_if_offline
patch_if_offline()
from utils.firebase_config import initialize_firebase
from agents.orchestrator import start_research
from tools.pinecone_tool import delete_report_chunks
from tools.credibility import rate_source_credibility
initialize_firebase()

def check_url_format(url: str) -> Dict[str, Any]:
    """Validate URL formats for citation checker."""
    if not isinstance(url, str) or not url.strip():
        return {"valid": False, "reason": "Empty or non-string URL", "domain": ""}
    
    url = url.strip()
    if not url.startswith("http"):
        return {"valid": False, "reason": "URL does not start with http/https", "domain": ""}
        
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    if not domain or "." not in domain:
        return {"valid": False, "reason": "No valid domain name", "domain": ""}
        
    if "localhost" in domain:
        return {"valid": False, "reason": "URL contains localhost", "domain": domain}
        
    if "example.com" in domain:
        return {"valid": False, "reason": "URL contains example.com", "domain": domain}
        
    if "placeholder" in domain or "test" in domain:
        return {"valid": False, "reason": "URL is a test/placeholder domain", "domain": domain}
        
    return {"valid": True, "reason": "Format is valid", "domain": domain}


def check_url_accessible(url: str) -> Dict[str, Any]:
    """Test URL accessibility with HEAD/GET fallbacks."""
    result = {
        "accessible": False,
        "status_code": 0,
        "final_url": url,
        "error": None
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=5.0) as client:
            # Try HEAD first
            try:
                res = client.head(url)
                if res.status_code in [405, 403, 401]:
                    res = client.get(url)
            except Exception:
                res = client.get(url)

            result["status_code"] = res.status_code
            result["accessible"] = res.status_code == 200
            result["final_url"] = str(res.url)
    except Exception as e:
        result["error"] = str(e)
        
    return result


def analyze_citation_quality(citations: List[str]) -> Dict[str, Any]:
    """Analyze a list of citation URLs and assess domain diversity and credibility."""
    total = len(citations)
    valid_format = 0
    accessible_count = 0
    unique_domains = set()
    
    credibility_counts = {
        "academic": 0,
        "news": 0,
        "blog": 0,
        "government": 0,
        "unknown": 0
    }

    for url in citations:
        # Check format
        fmt = check_url_format(url)
        if fmt["valid"]:
            valid_format += 1
            unique_domains.add(fmt["domain"])
            
            # Check accessibility (async fallback in tests, sync here)
            access = check_url_accessible(url)
            if access["accessible"]:
                accessible_count += 1
            else:
                print(f"  ⚠️  Citation not fully accessible (HEAD/GET failed): {url} (status: {access['status_code']}, err: {access['error']})")
                
            # Check credibility
            cred = rate_source_credibility(url)
            rating = cred.get("rating", "").lower()
            
            if "academic" in rating or "education" in rating:
                credibility_counts["academic"] += 1
            elif "news" in rating or "journalism" in rating or "media" in rating:
                credibility_counts["news"] += 1
            elif "government" in rating or "gov" in rating:
                credibility_counts["government"] += 1
            elif "blog" in rating or "opinion" in rating:
                credibility_counts["blog"] += 1
            else:
                credibility_counts["unknown"] += 1
        else:
            print(f"  ❌ Invalid citation format: {url} (Reason: {fmt['reason']})")

    domain_diversity = len(unique_domains) / total if total > 0 else 0.0

    return {
        "total": total,
        "valid_format": valid_format,
        "accessible": accessible_count,
        "unique_domains": list(unique_domains),
        "domain_diversity": domain_diversity,
        "credibility_breakdown": credibility_counts
    }


async def test_citations_for_topic(topic: str) -> Dict[str, Any]:
    """Execute research pipeline for topic and run citation analytics."""
    report_id = f"cite_test_{int(time.time())}"
    print(f"\n🚀 Running citation pipeline for topic: '{topic}'...")
    
    try:
        # Execute quick depth pipeline
        state = await start_research(
            report_id=report_id,
            topic=topic,
            depth="quick",
            language="english",
            user_id="citation_checker_user"
        )
        
        final_report = state.get_field("final_report", {})
        findings = final_report.get("key_findings", [])
        sources = final_report.get("sources", [])

        citations = []
        for f in findings:
            if isinstance(f, dict) and f.get("citation"):
                citations.append(f.get("citation"))
        for s in sources:
            if isinstance(s, dict) and s.get("url"):
                citations.append(s.get("url"))

        # Unique/deduplicated citations list
        citations = list(set(citations))
        
        analysis = analyze_citation_quality(citations)
        return analysis

    finally:
        print(f"🗑️  Cleaning up citation chunks: {report_id}...")
        try:
            delete_report_chunks(report_id)
        except Exception as e:
            print(f"Cleanup warning: {e}")


async def run_citation_tests():
    print("=" * 65)
    print("Citation Quality and Domain Diversity Verification Tests")
    print("=" * 65)

    topics = [
        "Machine learning in medicine",
        "Renewable energy trends"
    ]

    for topic in topics:
        result = await test_citations_for_topic(topic)
        
        print(f"\nTopic: {topic}")
        print(f"Citations found: {result['total']}")
        print(f"Valid format: {result['valid_format']}/{result['total']}")
        print(f"Accessible URLs: {result['accessible']}/{result['total']}")
        print(f"Unique domains: {len(result['unique_domains'])}")
        print(f"Domain diversity: {result['domain_diversity']:.0%}")
        print("Credibility breakdown:")
        for k, v in result['credibility_breakdown'].items():
            print(f"  {k}: {v}")
        print("─" * 65)

    print("\n✅ Citation tests complete")


if __name__ == "__main__":
    asyncio.run(run_citation_tests())
