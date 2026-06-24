"""AgentState memory management class for Multi-Agent Research Assistant.

This module provides thread-safe operations on the agent execution state,
rehydrates state from Firestore, and stores logs and summaries.
"""

from __future__ import annotations

import copy
import logging
import time
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentMemory:
    """Manages the AgentState lifecycle for a single research report execution.

    Uses thread locks to ensure safe parallel agent read/write access.
    """

    def __init__(
        self,
        report_id: str,
        topic: str = "",
        depth: str = "deep",
        language: str = "english",
        user_id: str = "",
    ) -> None:
        """Initialize a fresh AgentState dictionary with standard fields."""
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            # -- INPUT FIELDS --
            "report_id": report_id,
            "topic": topic,
            "depth": depth,
            "language": language,
            "user_id": user_id,

            # -- AGENT OUTPUTS --
            "sub_questions": [],
            "search_results": [],
            "summaries": [],
            "verified_claims": [],
            "final_report": {},
            "followup_questions": [],

            # -- UNIQUE FEATURE FIELDS --
            "confidence_score": 0,
            "source_credibility": [],
            "thinking_logs": [],

            # -- SYSTEM FIELDS --
            "status": "pending",
            "current_agent": None,
            "logs": [],
            "error": None,
        }

    def update_state(self, key: str, value: Any) -> bool:
        """Update a single field in the state after validating key existence."""
        with self._lock:
            if key not in self._state:
                logger.warning(f"Attempted to update invalid state key: '{key}'")
                return False
            self._state[key] = value
            return True

    def update_multiple(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """Update multiple fields concurrently. Returns dict of key -> success flag."""
        results = {}
        for key, value in updates.items():
            results[key] = self.update_state(key, value)
        return results

    def get_state(self) -> Dict[str, Any]:
        """Return a deep copy of the complete current state to prevent mutation."""
        with self._lock:
            return copy.deepcopy(self._state)

    def get_field(self, key: str, default: Any = None) -> Any:
        """Return the value of a single state field, defaulting if missing."""
        with self._lock:
            return self._state.get(key, default)

    def reset_state(self) -> None:
        """Reset all output and system status fields, retaining metadata inputs."""
        with self._lock:
            self._state["sub_questions"] = []
            self._state["search_results"] = []
            self._state["summaries"] = []
            self._state["verified_claims"] = []
            self._state["final_report"] = {}
            self._state["followup_questions"] = []
            self._state["confidence_score"] = 0
            self._state["source_credibility"] = []
            self._state["thinking_logs"] = []
            self._state["status"] = "pending"
            self._state["current_agent"] = None
            self._state["logs"] = []
            self._state["error"] = None

    def add_log(self, agent: str, status: str, message: str) -> None:
        """Append an execution log entry and print to standard output."""
        log_entry = {
            "agent": agent,
            "status": status,
            "message": message,
            "timestamp": int(time.time()),
        }
        with self._lock:
            self._state["logs"].append(log_entry)
        logger.info(f"[{agent.upper()}] Status: {status} | {message}")

    def add_thinking_log(self, agent: str, thought: str) -> None:
        """Append a thinking log entry (Unique Feature 4)."""
        log_entry = {
            "agent": agent,
            "thought": thought,
            "timestamp": int(time.time()),
        }
        with self._lock:
            self._state["thinking_logs"].append(log_entry)
        logger.debug(f"[{agent.upper()} THINKING] {thought}")

    def set_current_agent(self, agent_name: str) -> None:
        """Update the active agent and record an initialization log."""
        self.update_state("current_agent", agent_name)
        self.add_log(agent_name, "started", f"{agent_name} agent started execution")

    def set_status(self, status: str) -> None:
        """Validate and transition execution status (pending/running/done/failed)."""
        valid_statuses = {"pending", "running", "done", "failed"}
        if status not in valid_statuses:
            logger.warning(f"Invalid status value rejected: '{status}'")
            return

        current_status = self.get_field("status")
        if self.update_state("status", status):
            self.add_log(
                "system",
                "status_change",
                f"Pipeline status transitioned from '{current_status}' to '{status}'",
            )

    def set_error(self, error_message: str) -> None:
        """Set the error payload, flag status to failed, and add diagnostic logs."""
        self.update_state("error", error_message)
        self.set_status("failed")
        self.add_log("system", "error", f"Execution failed: {error_message}")

    def append_to_field(self, field: str, item: Any) -> bool:
        """Safely append an item to a list state field."""
        with self._lock:
            if field not in self._state:
                logger.warning(f"Field '{field}' does not exist in state")
                return False
            if not isinstance(self._state[field], list):
                logger.warning(f"Field '{field}' is not a list structure, append rejected")
                return False
            self._state[field].append(item)
            return True

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Retrieve a combined list of all sources across search results."""
        sources = []
        with self._lock:
            for result in self._state.get("search_results", []):
                if isinstance(result, dict) and "sources" in result:
                    sources.extend(result["sources"])
        return sources

    def get_all_summaries(self) -> List[Dict[str, Any]]:
        """Retrieve all generated sub-question summaries."""
        with self._lock:
            return list(self._state.get("summaries", []))

    def get_verified_claims_only(self) -> List[Dict[str, Any]]:
        """Filter and return only verified claims from the fact checker."""
        verified = []
        with self._lock:
            for claim in self._state.get("verified_claims", []):
                if isinstance(claim, dict) and claim.get("status") == "verified":
                    verified.append(claim)
        return verified

    def save_to_firestore(self) -> bool:
        """Save a subset of active execution fields to Firestore."""
        try:
            from utils.firebase_config import get_firestore

            db = get_firestore()
            report_id = self.get_field("report_id")
            doc_ref = db.collection("reports").document(report_id)

            logs = self.get_field("logs")
            last_50_logs = logs[-50:] if len(logs) > 50 else logs

            payload = {
                "topic": self.get_field("topic"),
                "depth": self.get_field("depth"),
                "language": self.get_field("language"),
                "status": self.get_field("status"),
                "confidence_score": self.get_field("confidence_score"),
                "final_report": self.get_field("final_report"),
                "logs": last_50_logs,
                "user_id": self.get_field("user_id"),
                "updated_at": int(time.time()),
            }

            doc_ref.set(payload, merge=True)
            logger.info("Successfully persisted AgentMemory to Firestore")
            return True
        except Exception as e:
            logger.warning(f"Defensive: Firestore save bypassed or failed: {e}")
            return False

    def load_from_firestore(self) -> bool:
        """Rehydrate state data from the Firestore collection."""
        try:
            from utils.firebase_config import get_firestore

            db = get_firestore()
            report_id = self.get_field("report_id")
            doc_ref = db.collection("reports").document(report_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict() or {}
                with self._lock:
                    for key in [
                        "topic",
                        "depth",
                        "language",
                        "status",
                        "confidence_score",
                        "final_report",
                        "logs",
                        "user_id",
                    ]:
                        if key in data:
                            self._state[key] = data[key]
                logger.info("Successfully rehydrated AgentMemory from Firestore")
                return True
            return False
        except Exception as e:
            logger.warning(f"Defensive: Firestore rehydration bypassed: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Return the complete state dictionary."""
        return self.get_state()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Compute structural metrics and completion numbers from state."""
        state = self.get_state()

        sub_questions = state.get("sub_questions") or []
        search_results = state.get("search_results") or []
        summaries = state.get("summaries") or []
        verified_claims = state.get("verified_claims") or []

        # Count total sources
        total_sources = 0
        for item in search_results:
            total_sources += len(item.get("sources") or [])

        # Count total chunks stored across summaries
        total_chunks = 0
        for item in summaries:
            total_chunks += item.get("chunk_count", 0)

        # Count verified vs unverified claims
        v_claims_count = 0
        uv_claims_count = 0
        for claim in verified_claims:
            if claim.get("status") == "verified":
                v_claims_count += 1
            else:
                uv_claims_count += 1

        return {
            "sub_questions_count": len(sub_questions),
            "total_sources": total_sources,
            "total_chunks_stored": total_chunks,
            "summaries_count": len(summaries),
            "verified_claims_count": v_claims_count,
            "unverified_claims_count": uv_claims_count,
            "confidence_score": state.get("confidence_score", 0),
            "status": state.get("status"),
            "current_agent": state.get("current_agent"),
        }

    @staticmethod
    def create_new(
        report_id: str,
        topic: str,
        depth: str = "deep",
        language: str = "english",
        user_id: str = "",
    ) -> AgentMemory:
        """Create a new AgentMemory instance and record it in database."""
        memory = AgentMemory(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language=language,
            user_id=user_id,
        )
        memory.save_to_firestore()
        return memory

    @staticmethod
    def load_existing(report_id: str) -> Optional[AgentMemory]:
        """Load an existing AgentMemory document from database. Returns None if not found."""
        memory = AgentMemory(report_id=report_id)
        if memory.load_from_firestore():
            return memory
        return None


# ==============================================================================
# STEP 6: HOW AGENTS WILL USE THESE FILES
# ==============================================================================
# ── HOW ORCHESTRATOR WILL USE THIS ──
# from memory.agent_memory import AgentMemory
# from utils.websocket_manager import ws_manager
#
# async def run(state: AgentMemory, report_id):
#   state.set_current_agent("orchestrator")
#   await ws_manager.emit_agent_start(
#     report_id, "orchestrator",
#     "Breaking topic into sub-questions..."
#   )
#   state.add_thinking_log("orchestrator",
#     f"Topic: {state.get_field('topic')}")
#   await ws_manager.emit_thinking(
#     report_id, "orchestrator",
#     "Analyzing topic complexity..."
#   )
#   sub_questions = generate_questions(
#     state.get_field("topic"),
#     state.get_field("depth")
#   )
#   state.update_state("sub_questions",
#     sub_questions)
#   state.add_log("orchestrator", "done",
#     f"Created {len(sub_questions)} questions")
#   await ws_manager.emit_agent_done(
#     report_id, "orchestrator",
#     f"Created {len(sub_questions)} sub-questions",
#     data={"sub_questions": sub_questions}
#   )

# ── HOW SEARCH AGENT WILL USE THIS ──
# async def run(state: AgentMemory, report_id):
#   state.set_current_agent("search_agent")
#   questions = state.get_field("sub_questions")
#   await ws_manager.emit_agent_start(
#     report_id, "search_agent",
#     f"Searching web for {len(questions)} questions"
#   )
#   results = search_all_questions(
#     questions, report_id
#   )
#   state.update_state("search_results", results)
#   await ws_manager.emit_agent_done(
#     report_id, "search_agent",
#     "Search complete"
#   )
