"""FollowUp Agent for the Multi-Agent Research Assistant.

This agent generates actionable follow-up research questions to deepen the user's
understanding of the topic, building upon the findings of the completed report.
"""

from __future__ import annotations

import os
import json
import re
import logging
import asyncio
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI

from memory.agent_memory import AgentMemory
from utils.websocket_manager import ws_manager

load_dotenv()
logger = logging.getLogger(__name__)

# Constants
MODEL = "gpt-4o-mini"
FOLLOWUP_COUNT = 5

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
        logger.info("OpenAI client successfully initialized in FollowUp Agent.")
        return _openai_client
    except Exception as exc:
        logger.exception("Failed to initialize OpenAI client in FollowUp Agent.")
        raise


def build_followup_prompt(
    topic: str,
    sub_questions: List[str],
    final_report: Dict[str, Any]
) -> tuple[str, str]:
    """Generates the system and user prompts for GPT-4o-mini.

    Args:
        topic: The original research topic.
        sub_questions: List of sub-questions already covered.
        final_report: The generated final report dict.

    Returns:
        A tuple of (system_prompt, user_prompt).
    """
    covered = "\n".join(f"- {q}" for q in sub_questions)
    title = final_report.get("title", topic)
    key_findings = final_report.get("key_findings", [])
    findings_str = "\n".join(f"- {f.get('point', '')}" for f in key_findings[:3])

    system_prompt = """You are a research advisor helping users explore topics more deeply. Generate specific, actionable follow-up research questions that build on completed research."""

    user_prompt = f"""A research report was just completed.

Topic: {topic}
Report Title: {title}

What was already covered:
{covered}

Key findings from the report:
{findings_str}

Generate {FOLLOWUP_COUNT} follow-up research questions that:
1. Are NOT covered in the existing research
2. Would deepen understanding of {topic}
3. Are specific enough to research with web sources
4. Progress from specific to broader context
5. Are genuinely interesting next steps

Return ONLY a JSON array of {FOLLOWUP_COUNT} question strings.
Example: ["Question 1?", "Question 2?"]"""

    return system_prompt, user_prompt


async def generate_followup_questions(
    state: AgentMemory,
    report_id: str
) -> List[str]:
    """Queries GPT-4o-mini to generate 5 deep follow-up questions.

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        A list of cleaned question strings.
    """
    topic = state.get_field("topic") or ""
    sub_questions = state.get_field("sub_questions", []) or []
    final_report = state.get_field("final_report", {}) or {}

    system_prompt, user_prompt = build_followup_prompt(topic, sub_questions, final_report)

    response_text = ""
    try:
        client = get_openai_client()

        for attempt in range(1, 3):
            try:
                logger.info(f"Calling OpenAI completion API for follow-up questions (attempt {attempt}/2)...")
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7
                )
                response_text = response.choices[0].message.content or ""
                if response_text.strip():
                    break
            except Exception as exc:
                logger.warning(f"Follow-up questions attempt {attempt} failed: {exc}")
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    raise
    except Exception as exc:
        logger.error(f"Error querying OpenAI for follow-up questions: {exc}")

    # Parse response
    questions: List[str] = []
    text_clean = response_text.strip()

    if text_clean:
        # Strategy 1: Direct JSON parse
        try:
            parsed = json.loads(text_clean)
            if isinstance(parsed, list):
                questions = [str(item) for item in parsed]
                logger.info("Direct JSON parse strategy succeeded in FollowUp Agent.")
        except Exception:
            pass

        # Strategy 2: Regex extract list block
        if not questions:
            try:
                match = re.search(r'\[.*\]', text_clean, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        questions = [str(item) for item in parsed]
                        logger.info("Regex JSON extraction strategy succeeded in FollowUp Agent.")
            except Exception:
                pass

        # Strategy 3: Split by newlines and clean list formats
        if not questions:
            try:
                lines = text_clean.split("\n")
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    cleaned = re.sub(r'^(?:\d+\.\s*|[-*+]\s*)', '', line_stripped).strip()
                    cleaned = cleaned.strip('"').strip("'").strip()
                    if len(cleaned) >= 15:
                        questions.append(cleaned)
                if questions:
                    logger.info("Newline split strategy succeeded in FollowUp Agent.")
            except Exception:
                pass

    # Strategy 4: Fallback questions if all parsing strategies fail
    if not questions:
        logger.warning("All parsing strategies failed. Generating default fallback questions.")
        questions = [
            f"What are the latest developments in {topic}?",
            f"How does {topic} vary globally?",
            f"What are expert predictions about the future of {topic}?",
            f"What are the main criticisms of current approaches to {topic}?",
            f"How does {topic} compare to alternative approaches?"
        ]

    # Clean, validate, and format questions
    cleaned_questions = []
    for q in questions:
        q_clean = q.strip()
        if q_clean:
            # Ensure it ends with a question mark
            if not q_clean.endswith("?"):
                q_clean += "?"
            if len(q_clean) > 15:
                cleaned_questions.append(q_clean)

    final_questions = cleaned_questions[:FOLLOWUP_COUNT]
    
    # Fill up to 5 questions if fewer are extracted
    while len(final_questions) < FOLLOWUP_COUNT:
        fillers = [
            f"What are the long-term societal impacts of {topic}?",
            f"How do regulatory policies affect development in {topic}?",
            f"What are the financial costs and investment trends in {topic}?",
            f"How does consumer behavior drive progress in {topic}?",
            f"What are the ethical boundaries surrounding {topic}?"
        ]
        for filler in fillers:
            if filler not in final_questions:
                final_questions.append(filler)
                break
        else:
            final_questions.append("What are the other emerging research areas?")

    logger.info(f"Generated {len(final_questions)} follow-up questions.")
    return final_questions


async def run(
    state: AgentMemory,
    report_id: str
) -> bool:
    """Entry point for the FollowUp Agent called by orchestrator run_pipeline().

    Args:
        state: Agent memory context.
        report_id: Unique string identifying the active report.

    Returns:
        Always returns True (soft-failure) to avoid blocking research completion.
    """
    try:
        state.set_current_agent("followup_agent")

        await ws_manager.emit_agent_start(
            report_id, "followup_agent",
            "Generating follow-up research questions..."
        )

        await ws_manager.emit_thinking(
            report_id, "followup_agent",
            "Analyzing report to find research gaps..."
        )

        state.add_thinking_log(
            "followup_agent",
            f"Generating {FOLLOWUP_COUNT} follow-up questions for: {state.get_field('topic')}"
        )

        questions = await generate_followup_questions(state, report_id)

        if not questions:
            logger.warning("No follow-up questions could be generated.")
            return True

        # Store in state
        state.update_state("followup_questions", questions)

        state.add_log(
            "followup_agent", "done",
            f"Generated {len(questions)} follow-up questions"
        )

        await ws_manager.emit_agent_done(
            report_id, "followup_agent",
            f"Generated {len(questions)} follow-up research questions",
            data={
                "questions": questions,
                "count": len(questions)
            }
        )

        return True

    except Exception as exc:
        logger.error(f"FollowUp Agent failed: {exc}", exc_info=True)
        # Soft failure: log warning but continue the pipeline
        return True
