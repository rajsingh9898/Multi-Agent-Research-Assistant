"""WebSocket connections manager for real-time agent execution updates.

Centralizes socket state tracking, schema-compliant messaging, and broadcast triggers.
"""

from __future__ import annotations

import time
import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket connections per report_id with thread safety."""

    def __init__(self) -> None:
        """Initialize empty connections registry and operational lock."""
        self.connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, report_id: str) -> None:
        """Accept connection, store socket reference, and emit confirmation payload."""
        await websocket.accept()
        async with self.lock:
            self.connections[report_id] = websocket

        logger.info(f"WebSocket connected: {report_id}")

        # Send immediate confirmation message
        await self.emit(
            report_id=report_id,
            event="connected",
            agent="system",
            message="Connected to research pipeline",
            data={"report_id": report_id},
        )

    async def disconnect(self, report_id: str) -> None:
        """Close registry reference for the disconnected report_id client."""
        async with self.lock:
            try:
                self.connections.pop(report_id, None)
                logger.info(f"WebSocket disconnected: {report_id}")
            except KeyError:
                pass

    async def emit(
        self,
        report_id: str,
        event: str,
        agent: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a schema-compliant message payload to a specific client."""
        async with self.lock:
            websocket = self.connections.get(report_id)

        if not websocket:
            logger.warning(f"Unable to emit event '{event}': client '{report_id}' not connected.")
            return

        payload = {
            "event": event,
            "agent": agent,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time()),
        }

        try:
            await websocket.send_json(payload)
        except Exception as exc:
            logger.error(f"WebSocket send failed for report '{report_id}'. Disconnecting... Error: {exc}")
            await self.disconnect(report_id)

    async def emit_thinking(self, report_id: str, agent: str, thought: str) -> None:
        """Specialized emitter for Feature 4 (Thinking Logs)."""
        await self.emit(
            report_id=report_id,
            event="thinking_log",
            agent=agent,
            message="Thinking...",
            data={"thought": thought},
        )

    async def emit_error(self, report_id: str, agent: str, message: str) -> None:
        """Specialized emitter for connection or agent error updates."""
        logger.error(f"Agent '{agent}' error on report '{report_id}': {message}")
        await self.emit(
            report_id=report_id,
            event="error",
            agent=agent,
            message=message,
        )

    async def emit_report_ready(self, report_id: str) -> None:
        """Specialized emitter when final research report compilation completes."""
        await self.emit(
            report_id=report_id,
            event="report_ready",
            agent="system",
            message="Research complete!",
            data={"report_id": report_id},
        )

    async def emit_agent_start(self, report_id: str, agent: str, message: str) -> None:
        """Shortcut to emit a pipeline agent_start notification."""
        await self.emit(
            report_id=report_id,
            event="agent_start",
            agent=agent,
            message=message,
        )

    async def emit_agent_update(
        self, report_id: str, agent: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Shortcut to emit an active agent progress update."""
        await self.emit(
            report_id=report_id,
            event="agent_update",
            agent=agent,
            message=message,
            data=data,
        )

    async def emit_agent_done(
        self, report_id: str, agent: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Shortcut to emit a pipeline agent completion event."""
        await self.emit(
            report_id=report_id,
            event="agent_done",
            agent=agent,
            message=message,
            data=data,
        )

    async def broadcast(self, event: str, message: str) -> None:
        """Broadcast system announcements to all active connection channels."""
        async with self.lock:
            active_ids = list(self.connections.keys())

        for report_id in active_ids:
            payload = {
                "event": event,
                "agent": "system",
                "message": message,
                "data": {},
                "timestamp": int(time.time()),
            }
            async with self.lock:
                websocket = self.connections.get(report_id)

            if websocket:
                try:
                    await websocket.send_json(payload)
                except Exception as exc:
                    logger.error(f"Broadcast failure on report '{report_id}': {exc}")
                    await self.disconnect(report_id)

    def is_connected(self, report_id: str) -> bool:
        """Return boolean connection status for report_id client."""
        return report_id in self.connections

    def get_connected_count(self) -> int:
        """Return total number of active connections."""
        return len(self.connections)


# Exported singleton instance
ws_manager = WebSocketManager()
