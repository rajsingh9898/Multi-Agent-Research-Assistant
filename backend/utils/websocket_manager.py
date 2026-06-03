"""Simple WebSocket manager for FastAPI
- Tracks connections per report_id and broadcasts events.
"""
from typing import Dict, List
from fastapi import WebSocket

CONNECTIONS: Dict[str, List[WebSocket]] = {}

async def connect(report_id: str, ws: WebSocket):
    await ws.accept()
    CONNECTIONS.setdefault(report_id, []).append(ws)

async def disconnect(report_id: str, ws: WebSocket):
    if report_id in CONNECTIONS and ws in CONNECTIONS[report_id]:
        CONNECTIONS[report_id].remove(ws)

async def broadcast(report_id: str, message: dict):
    for ws in CONNECTIONS.get(report_id, []):
        try:
            await ws.send_json(message)
        except Exception:
            pass
