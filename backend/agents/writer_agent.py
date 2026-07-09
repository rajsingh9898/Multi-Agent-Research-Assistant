"""Writer Agent for the Multi-Agent Research Assistant.

This agent takes all verified and uncertain claims from the FactCheck Agent,
and structures them into a comprehensive research report using GPT-4o-mini.
"""

from __future__ import annotations

import os
import json
import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from agents.factcheck_agent import get_verified_only
from tools.confidence import get_confidence_label
from utils.translator import (
    get_language_prompt,
    get_report_labels,
    validate_language
)
from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager

load_dotenv()
logger = logging.getLogger(__name__)

# Constants
MODEL = "gpt-4o-mini"
EXECUTIVE_SUMMARY_WORDS = 150
DETAILED_ANALYSIS_WORDS = 400
CONCLUSION_WORDS = 100
KEY_FINDINGS_COUNT = 7

# Singleton client reference
_openai_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Retrieve the singleton OpenAI client, validating that the API key exists.

    Raises:
        ValueError: If OPENAI_API_KEY is not configured in the environment.
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY is missing from environment variables.")
            raise ValueError("OPENAI_API_KEY environment variable is not configured.")

        # Clean surrounding quotes from env if any
        cleaned_key = api_key.strip().strip('"').strip("'")
        _openai_client = OpenAI(api_key=cleaned_key)
        logger.info("OpenAI client successfully initialized in Writer Agent.")
        return _openai_client
    except Exception as exc:
        logger.exception("Failed to initialize OpenAI client in Writer Agent.")
        raise


def build_context(state: AgentMemory) -> Dict[str, Any]:
    """Gathers claims, summaries, and credibility details to build LLM context.

    Args:
        state: Agent memory context.

    Returns:
        Structured context dictionary.
    """
    all_claims = state.get_field("verified_claims", []) or []
    summaries = state.get_all_summaries() or []
    topic = state.get_field("topic", "")
    language = state.get_field("language", "english")
    confidence = state.get_field("confidence_score", 0)
    sub_questions = state.get_field("sub_questions", [])
    source_credibility = state.get_field("source_credibility", []) or []

    # Separate claims by verification status
    verified = [c for c in all_claims if isinstance(c, dict) and c.get("status") == "verified"]
    uncertain = [c for c in all_claims if isinstance(c, dict) and c.get("status") == "uncertain"]

    # Fallback rules
    if len(verified) == 0:
        logger.warning("No verified claims found! Using uncertain claims as fallback.")
        verified = [c for c in all_claims if isinstance(c, dict) and c.get("status") in ["verified", "uncertain"]]
        # Clear uncertain to avoid listing them twice in the prompt
        uncertain = []

    # Format verified facts
    verified_facts_str = ""
    for i, claim in enumerate(verified, 1):
        sources = ", ".join(claim.get("supporting_sources", [])[:2])
        verified_facts_str += f"{i}. {claim.get('claim')} [Sources: {sources}]\n"

    # Format uncertain facts
    uncertain_facts_str = ""
    for i, claim in enumerate(uncertain, 1):
        sources = ", ".join(claim.get("supporting_sources", [])[:1])
        uncertain_facts_str += f"{i}. {claim.get('claim')} [Source: {sources}]\n"

    # Format summaries
    summaries_str = ""
    for i, summary in enumerate(summaries, 1):
        q = summary.get("question", "")
        s = summary.get("summary", "")
        summaries_str += f"\nResearch Area {i}: {q}\n{s}\n{'─'*40}\n"

    # Deduplicate and match credibility metadata for sources
    all_source_urls = set()
    source_details = []

    # Process URLs from claims
    for claim in (verified + uncertain):
        for url in claim.get("supporting_sources", []):
            if url and url not in all_source_urls:
                all_source_urls.add(url)
                
                # Try matching credibility metrics from search results
                cred_rating = "unknown"
                cred_icon = "❓"
                for src in source_credibility:
                    if src.get("url") == url or src.get("source_url") == url:
                        cred_rating = src.get("credibility") or src.get("rating") or "unknown"
                        cred_icon = src.get("credibility_icon") or src.get("icon") or "❓"
                        break
                
                source_details.append({
                    "url": url,
                    "credibility": cred_rating,
                    "credibility_icon": cred_icon
                })

    # Catch any remaining URLs from summaries that weren't captured in claims
    for summary in summaries:
        for url in summary.get("citations", []):
            if url and url not in all_source_urls:
                all_source_urls.add(url)
                
                cred_rating = "unknown"
                cred_icon = "❓"
                for src in source_credibility:
                    if src.get("url") == url or src.get("source_url") == url:
                        cred_rating = src.get("credibility") or src.get("rating") or "unknown"
                        cred_icon = src.get("credibility_icon") or src.get("icon") or "❓"
                        break
                
                source_details.append({
                    "url": url,
                    "credibility": cred_rating,
                    "credibility_icon": cred_icon
                })

    return {
        "topic": topic,
        "language": language,
        "confidence": confidence,
        "sub_questions": sub_questions,
        "verified_facts": verified_facts_str,
        "uncertain_facts": uncertain_facts_str,
        "summaries": summaries_str,
        "verified_count": len(verified),
        "uncertain_count": len(uncertain),
        "source_details": source_details,
        "total_sources": len(all_source_urls)
    }


def build_writer_prompt(context: Dict[str, Any]) -> tuple[str, str]:
    """Generates the system and user prompts for GPT-4o-mini.

    Args:
        context: Gathers formatting texts and statistics context.

    Returns:
        A tuple of (system_prompt, user_prompt).
    """
    language = context["language"]
    language_instruction = get_language_prompt(language)

    system_prompt = f"""You are an expert research writer and academic journalist. You write comprehensive, well-structured research reports.

STRICT RULES:
1. Use ONLY verified and uncertain facts provided. Never invent statistics.
2. Cite every specific fact inline: [Source: URL]. URLs must exactly match the ones provided in the source materials.
3. Uncertain facts must include caveat: "some evidence suggests..." or "according to limited sources..."
4. Write in formal academic style.
5. {language_instruction}
6. Every section must have real content based on provided facts."""

    disclaimer = ""
    # The warning uses verified facts count from the state before fallback was applied.
    # Note that context["verified_count"] is the count after fallback, but we also check if no verified facts originally existed
    if context.get("verified_count", 0) < 3:
        disclaimer = (
            "\n\nCRITICAL QUALITY NOTICE:\n"
            "There are fewer than 3 verified facts in the source data. You MUST write a prominent quality disclaimer "
            "paragraph at the start of the executive summary explaining that this report is based on limited or unverified "
            "early sources and should be treated with appropriate caution regarding verification depth."
        )

    user_prompt = f"""Write a comprehensive research report.{disclaimer}

TOPIC: {context['topic']}
CONFIDENCE LEVEL: {context['confidence']}%
LANGUAGE: {context['language']}

═══════════════════════════════
VERIFIED FACTS (cite freely):
═══════════════════════════════
{context['verified_facts']}

═══════════════════════════════
UNCERTAIN FACTS (use with caveat):
═══════════════════════════════
{context['uncertain_facts'] or 'None'}

═══════════════════════════════
RESEARCH SUMMARIES (background):
═══════════════════════════════
{context['summaries']}

═══════════════════════════════
REQUIRED REPORT STRUCTURE:
═══════════════════════════════

Return a JSON object with EXACTLY these keys:

{{
  "title": "engaging title for the report",
  
  "executive_summary": "150 word overview covering: what topic is, why it matters, key conclusion. Cite at least 2 facts.",
  
  "key_findings": [
    {{
      "point": "specific finding with number/data and inline citation like [Source: URL]",
      "citation": "https://source-url.com",
      "status": "verified"
    }},
    ... (5-7 findings, mix verified+uncertain)
  ],
  
  "detailed_analysis": "400+ word analysis. Discuss all research areas. Connect findings. Discuss implications. Cite every fact. Use paragraphs, not bullets.",
  
  "limitations": "100-150 words about: {context['uncertain_count']} uncertain claims, source diversity, what the research doesn't cover, and the confidence level meaning.",
  
  "conclusion": "100 word takeaway: restate key finding differently, practical implication, and future outlook."
}}

CRITICAL: Return ONLY valid JSON. No markdown wrappers (like ```json). No explanation. Just the JSON object."""

    return system_prompt, user_prompt


def clean_json_string(s: str) -> str:
    """Replaces raw literal newlines and control characters inside JSON strings with escaped counterparts."""
    result = []
    in_quote = False
    escape = False
    
    for char in s:
        if char == '"' and not escape:
            in_quote = not in_quote
            result.append(char)
        elif char == '\\' and not escape:
            escape = True
            result.append(char)
        else:
            if escape:
                escape = False
            
            if in_quote:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                else:
                    result.append(char)
            else:
                result.append(char)
                
    return "".join(result)


def parse_report_response(response_text: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tolerantly parses LLM output into a final report dictionary.

    Args:
        response_text: Raw LLM completion text.
        context: Gathers context metrics.

    Returns:
        Structured report dictionary or None on parsing failures.
    """
    if not response_text:
        return None

    cleaned_text = clean_json_string(response_text.strip())
    parsed_report: Optional[Dict[str, Any]] = None

    # Strategy 1: Direct JSON parse
    try:
        parsed_report = json.loads(cleaned_text)
        logger.info("Direct JSON parse strategy succeeded in Writer Agent.")
    except Exception:
        pass

    # Strategy 2: Regex extract first { ... } JSON block
    if not parsed_report:
        try:
            match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if match:
                parsed_report = json.loads(match.group(0))
                logger.info("Regex JSON extraction strategy succeeded in Writer Agent.")
            else:
                logger.warning("No JSON block found via regex match.")
        except Exception as exc:
            logger.warning(f"Regex parsing exception: {exc}")

    if not parsed_report:
        logger.error(f"Failed to parse report response as JSON using all strategies. Raw response was: {response_text}")
        return None

    # Validate required keys and populate with placeholders if missing
    required_keys = [
        "title", "executive_summary", "key_findings",
        "detailed_analysis", "limitations", "conclusion"
    ]
    for key in required_keys:
        if key not in parsed_report or not parsed_report[key]:
            logger.warning(f"Required report section '{key}' is missing. Filling with placeholder.")
            if key == "key_findings":
                parsed_report[key] = []
            else:
                parsed_report[key] = f"Section '{key}' placeholder content."

    # Validate key_findings type
    if not isinstance(parsed_report["key_findings"], list):
        parsed_report["key_findings"] = []

    # Calculate overall word count
    exec_sum_words = len(str(parsed_report.get("executive_summary", "")).split())
    analysis_words = len(str(parsed_report.get("detailed_analysis", "")).split())
    limitations_words = len(str(parsed_report.get("limitations", "")).split())
    conclusion_words = len(str(parsed_report.get("conclusion", "")).split())
    total_words = exec_sum_words + analysis_words + limitations_words + conclusion_words

    # Resolve confidence labels
    confidence = context["confidence"]
    label_info = get_confidence_label(confidence)

    # Attach metadata
    parsed_report["language"] = context["language"]
    parsed_report["word_count"] = total_words
    parsed_report["confidence_score"] = confidence
    parsed_report["confidence_label"] = label_info.get("label", "unknown")
    parsed_report["confidence_emoji"] = label_info.get("emoji", "❓")
    parsed_report["sub_questions_covered"] = context["sub_questions"]
    parsed_report["total_sources_used"] = context["total_sources"]
    parsed_report["sources"] = context["source_details"]
    parsed_report["generated_at"] = datetime.now(timezone.utc).isoformat()

    return parsed_report


async def write_report(
    state: AgentMemory,
    report_id: str
) -> bool:
    """Builds LLM prompts, generates, and parses the final research report.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        True if report was generated and stored successfully, else False.
    """
    try:
        state.set_current_agent("writer_agent")

        verified_claims_only = [
            c for c in (state.get_field("verified_claims", []) or [])
            if isinstance(c, dict) and c.get("status") == "verified"
        ]
        if len(verified_claims_only) < 3:
            state.add_thinking_log(
                "writer_agent",
                "Warning: Few verified claims. Report quality may be limited."
            )

        verified_claims = state.get_field("verified_claims", []) or []
        summaries = state.get_all_summaries() or []

        if not verified_claims and not summaries:
            state.set_error("No claims or summaries found to write report.")
            await ws_manager.emit_error(report_id, "writer_agent", "No verified claims or summaries.")
            return False

        # Emit start
        await ws_manager.emit_agent_start(
            report_id, "writer_agent",
            "Writing comprehensive research report..."
        )

        state.add_log("writer_agent", "start", "Beginning report generation")

        # Emit update
        await ws_manager.emit_agent_update(
            report_id, "writer_agent",
            "Building context from verified claims..."
        )

        context = build_context(state)

        # Emit thinking
        await ws_manager.emit_thinking(
            report_id, "writer_agent",
            f"Context ready: {context['verified_count']} verified, {context['uncertain_count']} "
            f"uncertain claims from {context['total_sources']} sources"
        )

        state.add_thinking_log(
            "writer_agent",
            f"Writing {context['language']} report. {context['verified_count']} verified + "
            f"{context['uncertain_count']} uncertain claims"
        )

        # Build prompts
        system_prompt, user_prompt = build_writer_prompt(context)

        # Emit update
        await ws_manager.emit_agent_update(
            report_id, "writer_agent",
            "Generating report with GPT-4o..."
        )

        client = get_openai_client()
        response_text = None

        for attempt in range(1, 4):
            try:
                logger.info(f"Calling OpenAI completion API for report generation (attempt {attempt}/3)...")
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.4
                )
                response_text = response.choices[0].message.content or ""
                if response_text.strip():
                    break
            except Exception as exc:
                logger.warning(f"Report generation attempt {attempt} failed: {exc}")
                if attempt < 3:
                    await asyncio.sleep(3)
                else:
                    raise

        if not response_text:
            state.set_error("GPT-4o completion returned empty text.")
            return False

        # Parse response
        report = parse_report_response(response_text, context)

        if not report:
            state.set_error("Failed to parse report response as JSON.")
            await ws_manager.emit_error(report_id, "writer_agent", "Report parsing failed.")
            return False

        # Add report_id to report structure
        report["report_id"] = report_id

        # Save to state
        state.update_state("final_report", report)

        word_count = report.get("word_count", 0)

        # Emit thinking
        await ws_manager.emit_thinking(
            report_id, "writer_agent",
            f"Report generated: {word_count} words, 6 sections, language: {context['language']}"
        )

        state.add_log(
            "writer_agent", "done",
            f"Report written: {word_count} words"
        )

        # Emit done
        await ws_manager.emit_agent_done(
            report_id, "writer_agent",
            f"Report complete: {word_count} words, 6 sections",
            data={
                "word_count": word_count,
                "sections": 6,
                "language": context["language"],
                "confidence_score": context["confidence"],
                "key_findings_count": len(report.get("key_findings", []))
            }
        )

        return True

    except Exception as exc:
        error_msg = f"Writer Agent failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "writer_agent", error_msg)
        return False
