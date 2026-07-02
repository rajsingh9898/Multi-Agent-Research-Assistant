"""WebSocket connections manager for real-time agent execution updates.

Centralizes socket state tracking, schema-compliant messaging, connection metadata,
reconnection support (with history replay), and broadcast triggers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Represents connection metadata for an active client socket."""
    websocket: WebSocket
    report_id: str
    connected_at: float
    events_sent: int = 0
    last_ping: float = 0.0


class WebSocketManager:
    """Manages active WebSocket connections per report_id with thread safety and event history."""

    def __init__(self) -> None:
        """Initialize empty connections registry, event history queues, and operational lock."""
        # Active connections mapping report_id to ConnectionInfo
        self.connections: Dict[str, ConnectionInfo] = {}

        # Event history per report_id (stores last 100 events for client reconnection)
        self.event_history: Dict[str, deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=100))

        # Lock to ensure thread safety
        self.lock = asyncio.Lock()

        logger.info("WebSocketManager initialized")

    async def connect(self, websocket: WebSocket, report_id: str) -> None:
        """Accepts connection, stores socket reference, and replays missed events from history."""
        await websocket.accept()

        async with self.lock:
            # Store connection info
            self.connections[report_id] = ConnectionInfo(
                websocket=websocket,
                report_id=report_id,
                connected_at=time.time()
            )

        # Send immediate connected event confirmation
        await self._send_to_socket(
            websocket,
            {
                "event": "connected",
                "agent": "system",
                "message": "Connected to research pipeline",
                "data": {
                    "report_id": report_id,
                    "history_available": len(self.event_history[report_id])
                },
                "timestamp": int(time.time() * 1000)
            }
        )

        # Replay missed events if any exist (e.g. client reconnected)
        history = list(self.event_history[report_id])
        if history:
            logger.info(f"Replaying {len(history)} events for client {report_id}")
            for event in history:
                await self._send_to_socket(websocket, event)

        logger.info(f"WS connected: {report_id} (total active: {len(self.connections)})")

    async def disconnect(self, report_id: str) -> None:
        """Closes registry reference for the disconnected report_id client."""
        async with self.lock:
            if report_id in self.connections:
                del self.connections[report_id]
                logger.info(f"WS disconnected: {report_id}")

    async def _send_to_socket(self, websocket: WebSocket, message: Dict[str, Any]) -> bool:
        """Safely sends a JSON payload to a WebSocket without raising exceptions.

        Returns:
            True on success, False on failure.
        """
        try:
            # Check if connection state is open
            if websocket.client_state != WebSocketState.CONNECTED:
                return False
            await websocket.send_json(message)
            return True
        except Exception as exc:
            logger.debug(f"Send failed over WebSocket: {type(exc).__name__}")
            return False

    async def emit(
        self,
        report_id: str,
        event: str,
        agent: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Sends a schema-compliant message payload to a specific client and saves to history.

        Returns:
            True if sent successfully, False if client is not connected.
        """
        # Build schema-compliant event payload using unix millisecond timestamps
        msg = {
            "event": event,
            "agent": agent,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }

        # Store in event history registry even if client isn't connected to support reconnection replay
        self.event_history[report_id].append(msg)

        # Retrieve connection details
        conn_info = self.connections.get(report_id)
        if not conn_info:
            logger.debug(f"No WS connection for {report_id}, event stored in history queue.")
            return False

        success = await self._send_to_socket(conn_info.websocket, msg)

        if success:
            conn_info.events_sent += 1
        else:
            # Clean up stale connection
            await self.disconnect(report_id)

        return success

    async def emit_thinking(self, report_id: str, agent: str, thought: str) -> bool:
        """Emits an agent thinking log message (Feature 4)."""
        return await self.emit(
            report_id=report_id,
            event="thinking_log",
            agent=agent,
            message="Agent reasoning step",
            data={"thought": thought}
        )

    async def emit_error(self, report_id: str, agent: str, message: str) -> bool:
        """Emits an execution error event payload and prints it to application logs."""
        logger.error(f"WS error event: [{agent}] {message}")
        return await self.emit(
            report_id=report_id,
            event="error",
            agent=agent,
            message=message,
            data={"error": message}
        )

    async def emit_report_ready(self, report_id: str) -> bool:
        """Emits report completion ready event notification."""
        logger.info(f"Report ready: {report_id}")
        return await self.emit(
            report_id=report_id,
            event="report_ready",
            agent="system",
            message="Research complete! Report ready.",
            data={"report_id": report_id}
        )

    async def emit_agent_start(self, report_id: str, agent: str, message: str) -> bool:
        """Shortcut helper to broadcast agent startup."""
        return await self.emit(
            report_id=report_id,
            event="agent_start",
            agent=agent,
            message=message
        )

    async def emit_agent_update(
        self,
        report_id: str,
        agent: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Shortcut helper to broadcast agent execution updates."""
        return await self.emit(
            report_id=report_id,
            event="agent_update",
            agent=agent,
            message=message,
            data=data
        )

    async def emit_agent_done(
        self,
        report_id: str,
        agent: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Shortcut helper to broadcast agent completion updates."""
        return await self.emit(
            report_id=report_id,
            event="agent_done",
            agent=agent,
            message=message,
            data=data
        )

    async def broadcast(
        self,
        event: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Broadcasts system notifications to all connected client WebSockets.

        Returns:
            Number of successful transmissions.
        """
        msg = {
            "event": event,
            "agent": "system",
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }

        sent_count = 0
        failed_ids = []

        # Thread-safe copy of connections
        async with self.lock:
            active_connections = list(self.connections.items())

        for report_id, conn_info in active_connections:
            success = await self._send_to_socket(conn_info.websocket, msg)
            if success:
                sent_count += 1
            else:
                failed_ids.append(report_id)

        # Disconnect failed connections
        for report_id in failed_ids:
            await self.disconnect(report_id)

        return sent_count

    def is_connected(self, report_id: str) -> bool:
        """Returns True if the report_id is currently connected."""
        return report_id in self.connections

    def get_connected_count(self) -> int:
        """Returns total active connection count."""
        return len(self.connections)

    def get_event_history(self, report_id: str) -> List[Dict[str, Any]]:
        """Returns a list of all replayed/stored event history dictionaries for a report_id."""
        return list(self.event_history.get(report_id, []))

    def clear_event_history(self, report_id: str) -> None:
        """Clears stored event history deque for a report_id."""
        if report_id in self.event_history:
            del self.event_history[report_id]
        logger.info(f"Event history cleared: {report_id}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Returns diagnostic statistics of connections registry and stored histories."""
        stats = {
            "active_connections": len(self.connections),
            "reports_with_history": len(self.event_history),
            "connections": []
        }

        for report_id, info in self.connections.items():
            stats["connections"].append({
                "report_id": report_id,
                "connected_seconds": int(time.time() - info.connected_at),
                "events_sent": info.events_sent
            })

        return stats


# Exported singleton instance
ws_manager = WebSocketManager()
