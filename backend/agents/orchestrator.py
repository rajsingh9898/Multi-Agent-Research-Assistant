"""Orchestrator Agent for the Multi-Agent Research Assistant.

This agent breaks down research topics into structured, searchable sub-questions
based on requested depth and handles the multi-agent pipeline orchestration.
"""

from __future__ import annotations

import os
import json
import re
import logging
import asyncio
from typing import List, Tuple, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager
from utils.translator import validate_language
from tools.confidence import calculate_confidence_score

load_dotenv()

logger = logging.getLogger(__name__)

# Constants
DEPTH_QUESTION_COUNT: Dict[str, int] = {
    "quick": 3,
    "deep": 4,
    "expert": 6
}
DEFAULT_DEPTH: str = "deep"
MODEL: str = "gpt-4o-mini"

# Singleton client reference
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Retrieve the singleton OpenAI client, validating that the API key exists.

    Raises:
        ValueError: If OPENAI_API_KEY is not configured in the environment.
    """
    global _client
    if _client is not None:
        return _client

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY is missing from environment variables.")
            raise ValueError("OPENAI_API_KEY environment variable is not configured.")

        # Clean surrounding quotes from env if any
        cleaned_key = api_key.strip().strip('"').strip("'")
        _client = OpenAI(api_key=cleaned_key)
        logger.info("OpenAI client successfully initialized in orchestrator.")
        return _client
    except Exception as exc:
        logger.exception("Failed to initialize OpenAI client in orchestrator.")
        raise


def get_question_count(depth: str) -> int:
    """Determine the number of sub-questions to generate based on requested depth.

    Args:
        depth: The depth string ('quick', 'deep', or 'expert').

    Returns:
        The expected number of questions.
    """
    try:
        if not depth:
            logger.warning("Empty depth provided. Defaulting to 'deep'.")
            return DEPTH_QUESTION_COUNT[DEFAULT_DEPTH]

        d_clean = depth.strip().lower()
        if d_clean not in DEPTH_QUESTION_COUNT:
            logger.warning(f"Unknown depth '{depth}' requested. Defaulting to 'deep'.")
            return DEPTH_QUESTION_COUNT[DEFAULT_DEPTH]

        return DEPTH_QUESTION_COUNT[d_clean]
    except Exception as exc:
        logger.exception(f"Error mapping depth '{depth}'. Falling back to default.")
        return DEPTH_QUESTION_COUNT[DEFAULT_DEPTH]


def build_orchestrator_prompt(
    topic: str, question_count: int, language: str
) -> Tuple[str, str]:
    """Build the system and user prompts for OpenAI.

    Args:
        topic: The primary research topic.
        question_count: The number of questions to generate.
        language: The target report language.

    Returns:
        A tuple of (system_prompt, user_prompt).
    """
    try:
        system_prompt = (
            "You are an expert research analyst and academic librarian. "
            "Your job is to break down complex research topics into specific, searchable sub-questions."
        )

        user_prompt = (
            f"Research Topic: {topic}\n"
            f"Required Question Count: {question_count}\n\n"
            "Instructions for question quality:\n"
            "- Each question must be specific enough to search the web for\n"
            "- Questions must not overlap\n"
            "- Together they cover topic fully\n"
            "- Progress from foundational to advanced\n"
            "- Each must be answerable with real web sources\n"
            "- No opinion questions, only factual research questions\n\n"
        )

        validated_lang = validate_language(language)
        if validated_lang != "english":
            user_prompt += (
                "Write the questions in English "
                "(questions will be searched in English regardless of report language)\n\n"
            )

        user_prompt += (
            "Output format instruction:\n"
            "Return ONLY a valid JSON array. No explanations. No numbering. "
            "No markdown. Just the JSON array.\n"
            'Example: ["question1", "question2"]'
        )

        return system_prompt, user_prompt
    except Exception as exc:
        logger.exception("Error building orchestrator prompts.")
        raise


def parse_questions_from_response(
    response_text: str, expected_count: int
) -> List[str]:
    """Parse GPT response into a list of cleaned question strings.

    Tries multiple parsing strategies (Direct JSON, regex extraction, newline split, fallback).
    """
    try:
        if not response_text:
            logger.warning("Empty response received to parse.")
            return []

        text_clean = response_text.strip()
        questions: List[str] = []

        # Strategy 1: Direct JSON parse
        try:
            parsed = json.loads(text_clean)
            if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
                questions = parsed
                logger.info("Direct JSON parse strategy succeeded.")
        except Exception as e:
            logger.debug(f"Direct JSON parse failed: {e}")

        # Strategy 2: Extract JSON array with regex
        if not questions:
            try:
                match = re.search(r'\[.*\]', text_clean, re.DOTALL)
                if match:
                    array_str = match.group(0)
                    parsed = json.loads(array_str)
                    if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
                        questions = parsed
                        logger.info("Regex JSON extraction strategy succeeded.")
            except Exception as e:
                logger.debug(f"Regex JSON extraction failed: {e}")

        # Strategy 3: Split by newlines
        if not questions:
            try:
                lines = text_clean.split("\n")
                parsed_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    # Strip standard list number prefix (e.g. "1. ", "- ", "* ")
                    cleaned = re.sub(r'^(?:\d+\.\s*|[-*+]\s*)', '', line_stripped).strip()
                    cleaned = cleaned.strip('"').strip("'").strip()
                    if "?" in cleaned:
                        parsed_lines.append(cleaned)
                if parsed_lines:
                    questions = parsed_lines
                    logger.info("Newline splitting strategy succeeded.")
            except Exception as e:
                logger.debug(f"Newline split parsing failed: {e}")

        # Strategy 4: Fallback
        if not questions:
            logger.error(f"All parsing strategies failed. Full response: '{response_text}'")
            return []

        # Filter empty strings and strip
        final_questions = [q.strip() for q in questions if q.strip()]

        if len(final_questions) > expected_count:
            logger.info(f"Trimming parsed questions from {len(final_questions)} to {expected_count}")
            final_questions = final_questions[:expected_count]
        elif len(final_questions) < expected_count:
            logger.warning(f"Got {len(final_questions)} questions, expected {expected_count}")

        return final_questions

    except Exception as exc:
        logger.exception("Unexpected error during response parsing.")
        return []


async def generate_sub_questions(
    state: AgentMemory, report_id: str
) -> List[str]:
    """Orchestrator sub-questions generation flow with retries and fallbacks.

    Args:
        state: Agent memory context object.
        report_id: Unique string identifying the research report.

    Returns:
        List of generated sub-questions.
    """
    try:
        topic = state.get_field("topic", "")
        depth = state.get_field("depth", DEFAULT_DEPTH)
        language = state.get_field("language", "english")

        validated_lang = validate_language(language)
        question_count = get_question_count(depth)

        await ws_manager.emit_thinking(
            report_id, "orchestrator", f"Analyzing topic: {topic[:50]}"
        )
        await ws_manager.emit_agent_update(
            report_id, "orchestrator", f"Generating {question_count} research questions..."
        )

        system_prompt, user_prompt = build_orchestrator_prompt(
            topic, question_count, validated_lang
        )

        attempts = 3
        response_text = ""
        openai_client = None
        api_failed = False
        api_error_details = ""

        try:
            openai_client = get_openai_client()
        except Exception as e:
            logger.error(f"OpenAI Client initialization failed: {e}")
            api_failed = True
            api_error_details = str(e)

        if not api_failed and openai_client:
            for attempt in range(1, attempts + 1):
                try:
                    logger.info(f"Calling OpenAI chat completions API (attempt {attempt}/3)...")
                    response = openai_client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                    )
                    response_text = response.choices[0].message.content or ""
                    if response_text.strip():
                        break
                    else:
                        raise ValueError("Received empty response from OpenAI API.")
                except Exception as exc:
                    logger.warning(f"Attempt {attempt} failed: {exc}")
                    if attempt == 1:
                        await asyncio.sleep(2)
                    elif attempt == 2:
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"All {attempts} API calls failed: {exc}")
                        api_failed = True
                        api_error_details = str(exc)

        questions = []
        if not api_failed and response_text:
            questions = parse_questions_from_response(response_text, question_count)

        if api_failed or not questions:
            if api_failed:
                error_msg = f"Failed to generate questions: {api_error_details}"
                state.set_error(error_msg)
                await ws_manager.emit_error(report_id, "orchestrator", error_msg)
            
            logger.warning("Using fallback questions.")
            questions = [
                f"What is {topic} and why does it matter?",
                f"What are the main benefits of {topic}?",
                f"What are the key challenges in {topic}?",
                f"What is the future outlook for {topic}?"
            ]
            questions = questions[:question_count]

        # Update execution state
        state.update_state("sub_questions", questions)
        state.add_log("orchestrator", "done", f"Created {len(questions)} sub-questions")
        state.add_thinking_log("orchestrator", f"Generated questions: {questions}")

        await ws_manager.emit_agent_done(
            report_id, "orchestrator",
            f"Created {len(questions)} research questions",
            data={"sub_questions": questions, "question_count": len(questions)}
        )

        return questions

    except Exception as exc:
        logger.exception("Failed in generate_sub_questions execution flow.")
        error_msg = f"Failed inside generate_sub_questions: {exc}"
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "orchestrator", error_msg)
        return []


async def run_pipeline(
    state: AgentMemory, report_id: str
) -> AgentMemory:
    """Master research pipeline coordinating all research agents in sequence.

    Args:
        state: Agent memory context.
        report_id: Unique report execution ID.

    Returns:
        The updated AgentMemory instance.
    """
    try:
        topic = state.get_field("topic", "")
        depth = state.get_field("depth", DEFAULT_DEPTH)

        # -- SETUP --
        state.set_status("running")
        state.set_current_agent("orchestrator")

        await ws_manager.emit(
            report_id, "research_start",
            "system", "Starting research pipeline...",
            data={"topic": topic, "depth": depth}
        )

        # -- STEP 1: ORCHESTRATOR --
        await ws_manager.emit_agent_start(
            report_id, "orchestrator",
            "Analyzing topic and creating research plan..."
        )

        questions = await generate_sub_questions(state, report_id)

        if not questions:
            state.set_error("No questions generated")
            await ws_manager.emit_error(report_id, "orchestrator", "Failed to generate plan.")
            return state

        # -- STEP 2: SEARCH AGENT --
        from agents.search_agent import run as search_run
        search_success = await search_run(state, report_id)

        if not search_success:
            logger.error("Search agent failed, stopping pipeline")
            return state

        search_results = state.get_field("search_results")
        total_sources = sum(
            r.get("source_count", 0)
            for r in search_results
        )
        logger.info(
            f"Search complete: {total_sources} sources found"
        )

        # -- STEP 3: SUMMARY AGENT (Full) --
        state.set_current_agent("summary_agent")
        from agents.summary_agent import run as summary_run
        summary_success = await summary_run(state, report_id)

        if not summary_success:
            logger.error("Summary Agent failed, stopping pipeline")
            return state

        summaries = state.get_field("summaries")
        logger.info(
            f"Summary complete: {len(summaries)} summaries generated"
        )

        # -- STEP 4: FACTCHECK AGENT --
        state.set_current_agent("factcheck_agent")
        from agents.factcheck_agent import run as fc_run
        fc_success = await fc_run(state, report_id)

        if not fc_success:
            logger.error("FactCheck Agent failed, stopping pipeline")
            return state

        verified = state.get_field("verified_claims", [])
        confidence = state.get_field("confidence_score", 0)
        logger.info(
            f"FactCheck complete: {len(verified)} claims, confidence: {confidence}%"
        )

        # ── STEP 5: WRITER AGENT ──
        state.set_current_agent("writer_agent")
        from agents.writer_agent import \
            write_report as writer_run
        writer_success = await writer_run(
            state, report_id
        )

        if not writer_success:
            logger.error("Writer Agent failed")
            return state

        report = state.get_field("final_report")
        logger.info(
            f"Report written: "
            f"{report.get('word_count',0)} words"
        )

        # ── STEP 6: FOLLOWUP AGENT ──
        state.set_current_agent("followup_agent")
        from agents.followup_agent import \
            run as followup_run
        await followup_run(state, report_id)

        followup = state.get_field(
            "followup_questions", []
        )
        logger.info(
            f"Follow-up questions: {len(followup)}"
        )

        # ── STEP 7: FINAL CONFIDENCE SCORE ──
        from tools.confidence import \
            calculate_confidence_score
        final_confidence = calculate_confidence_score(
            state.get_state()
        )
        state.update_state(
            "confidence_score", final_confidence
        )
        logger.info(
            f"Final confidence: {final_confidence}%"
        )

        # ── STEP 8: SAVE TO FIRESTORE ──
        state.set_status("done")
        state.add_log("system", "done",
            "Research pipeline complete")
        state.save_to_firestore()

        # ── STEP 9: NOTIFY FRONTEND ──
        await ws_manager.emit_report_ready(report_id)

        logger.info(
            f"Pipeline complete for: "
            f"{state.get_field('topic')}"
        )

        return state

    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}"
        logger.exception(error_msg)
        state.set_error(error_msg)
        await ws_manager.emit_error(report_id, "system", error_msg)
        state.save_to_firestore()
        return state


async def start_research(
    report_id: str, topic: str, depth: str, language: str, user_id: str
) -> AgentMemory:
    """API entrance function: builds AgentMemory and runs pipeline.

    Args:
        report_id: Unique string identifier for the report.
        topic: The query/research topic.
        depth: "quick", "deep", or "expert".
        language: Language of report output.
        user_id: Owner user's ID.

    Returns:
        The finished AgentMemory state.
    """
    try:
        # Create and persist starting memory state
        state = AgentMemory.create_new(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language=language,
            user_id=user_id
        )

        # Execute coordinates
        final_state = await run_pipeline(state, report_id)
        return final_state
    except Exception as exc:
        logger.exception("Unhandled error inside start_research endpoint coordinator.")
        # Create dummy/error state to write fallback log
        fallback_state = AgentMemory(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language=language,
            user_id=user_id
        )
        fallback_state.set_error(str(exc))
        fallback_state.save_to_firestore()
        return fallback_state
