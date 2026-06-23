"""FastAPI application entry point for Multi-Agent Research Assistant.

This module wires together:
- Firebase initialization on startup
- Firebase auth login and user profile persistence
- Protected API endpoints for research/report workflows
- WebSocket placeholder endpoint for live agent updates
- OpenAPI metadata and health checks
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tools.confidence import calculate_confidence_score, get_confidence_label
from tools.credibility import calculate_average_credibility, rate_source_credibility
from tools.pinecone_tool import get_index_stats, get_openai_client, get_pinecone_client
from tools.tavily_tool import search
from utils.auth import save_user_to_firestore, verify_token
from utils.firebase_config import initialize_firebase
from utils.websocket_manager import connect, disconnect

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

API_TITLE = "Multi-Agent Research Assistant"
API_VERSION = "1.0.0"
API_DESCRIPTION = "FastAPI backend for a multi-agent research assistant with Firebase auth, reports, and live updates."

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS is intentionally broad in development and should be narrowed in production.
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthLoginRequest(BaseModel):
    """Request body for Firebase login exchange."""

    id_token: str = Field(..., description="Firebase ID token returned by the client SDK")


class AuthUserResponse(BaseModel):
    """Normalized authenticated user payload returned by the backend."""

    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    email_verified: bool = False
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class ResearchStartRequest(BaseModel):
    """Request body to start a new research run."""

    topic: str = Field(..., min_length=2)
    depth: str = Field("deep", description="quick | deep | expert")
    language: str = Field("english", description="english | hindi | spanish")


class ResearchStatusResponse(BaseModel):
    """Response returned when a research run is created or queried."""

    report_id: str
    status: str
    current_agent: Optional[str] = None
    progress: int = 0


class ReportDataResponse(BaseModel):
    """Stored report data returned from the API."""

    report_id: str
    user_id: str
    topic: str
    depth: str
    language: str
    status: str
    confidence_score: int = 0
    source_credibility: List[Dict[str, Any]] = Field(default_factory=list)
    thinking_logs: List[Dict[str, Any]] = Field(default_factory=list)
    followup_questions: List[str] = Field(default_factory=list)
    report_markdown: str = ""
    created_at: str
    completed_at: Optional[str] = None


class PDFExportRequest(BaseModel):
    """Request body for generating a PDF from a report."""

    report_id: str


class WebSocketMessage(BaseModel):
    """Simple schema for placeholder WebSocket events."""

    event: str
    agent: Optional[str] = None
    message: Optional[str] = None
    thought: Optional[str] = None
    report_id: Optional[str] = None


# In-memory storage keeps the starter project runnable before Firestore wiring is complete.
REPORT_STORE: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize Firebase once when the application starts."""
    try:
        initialize_firebase()
        logger.info("Firebase initialization completed")
    except Exception as exc:
        logger.warning("Firebase initialization failed during startup: %s", exc)
        logger.warning("Continuing startup so the rest of the project can run")


@app.get("/healthz", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """Return a lightweight health check response for uptime monitoring."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/health/pinecone", tags=["health"])
async def health_pinecone() -> Dict[str, Any]:
    """Return Pinecone index health and readiness information."""
    stats = get_index_stats()
    return {
        "service": "pinecone",
        "status": stats.get("status", "unknown"),
        "ready": stats.get("status") not in {"error", "unknown"},
        "stats": stats,
    }


@app.get("/api/health/tavily", tags=["health"])
async def health_tavily() -> Dict[str, Any]:
    """Return Tavily Search API health and connectivity status."""
    api_key = os.getenv("TAVILY_API_KEY")
    api_key_configured = bool(api_key and api_key.strip())

    if not api_key_configured:
        return {
            "status": "error",
            "api_key_configured": False,
            "test_search_results": 0,
            "message": "TAVILY_API_KEY is not configured in .env file."
        }

    try:
        # Execute a test search query to verify Tavily connectivity
        results = search(query="test query", max_results=1, search_depth="basic")
        return {
            "status": "healthy",
            "api_key_configured": True,
            "test_search_results": len(results),
            "message": "Tavily search tool is online and fully configured."
        }
    except Exception as exc:
        logger.exception("Tavily health check search failed")
        return {
            "status": "error",
            "api_key_configured": True,
            "test_search_results": 0,
            "message": f"Tavily search connection error: {exc}"
        }


@app.get("/api/health/all", tags=["health"])
async def health_all() -> Dict[str, Any]:
    """Return a consolidated status payload for all configured services."""
    services: Dict[str, Dict[str, Any]] = {}

    try:
        initialize_firebase()
        services["firebase"] = {"status": "ready", "message": "Firebase initialized"}
    except Exception as exc:
        services["firebase"] = {"status": "error", "message": str(exc)}

    try:
        get_openai_client()
        services["openai"] = {"status": "ready", "message": "OpenAI client initialized"}
    except Exception as exc:
        services["openai"] = {"status": "error", "message": str(exc)}

    try:
        get_pinecone_client()
        services["pinecone"] = {"status": "ready", "message": "Pinecone client initialized", "stats": get_index_stats()}
    except Exception as exc:
        services["pinecone"] = {"status": "error", "message": str(exc), "stats": get_index_stats()}

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    services["tavily"] = {
        "status": "ready" if tavily_api_key else "missing",
        "message": "Tavily API key configured" if tavily_api_key else "TAVILY_API_KEY is not set",
    }

    sample_sources = [
        rate_source_credibility("https://www.nature.com/articles/d41586-024-00001-0"),
        rate_source_credibility("https://www.reuters.com/world/"),
    ]
    sample_state = {
        "source_credibility": sample_sources,
        "verified_claims": [{"verified": True}, {"verified": False}],
    }

    return {
        "service": "all",
        "status": "ready"
        if all(item["status"] == "ready" for item in services.values())
        else "degraded",
        "services": services,
        "confidence_example": {
            "score": calculate_confidence_score(sample_state),
            "label": get_confidence_label(calculate_confidence_score(sample_state)),
            "average_credibility": calculate_average_credibility(sample_sources),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/auth/login", response_model=AuthUserResponse, tags=["auth"])
async def login_user(payload: AuthLoginRequest) -> AuthUserResponse:
    """Verify a Firebase ID token and create/update the corresponding user profile."""
    # Reuse the dependency logic by passing the bearer token into verify_token.
    try:
        from firebase_admin import auth as firebase_auth

        decoded = firebase_auth.verify_id_token(payload.id_token)
        user = {
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "picture": decoded.get("picture"),
            "email_verified": decoded.get("email_verified", False),
        }
        saved_user = save_user_to_firestore(user)
        return AuthUserResponse(
            uid=saved_user["uid"],
            email=saved_user.get("email"),
            display_name=saved_user.get("displayName"),
            photo_url=saved_user.get("photoURL"),
            email_verified=bool(saved_user.get("emailVerified", False)),
            created_at=saved_user.get("createdAtClient"),
            last_login_at=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Login failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to verify Firebase token") from exc


@app.get("/api/auth/me", response_model=AuthUserResponse, tags=["auth"])
async def get_me(current_user: Dict[str, Any] = Depends(verify_token)) -> AuthUserResponse:
    """Return the current authenticated user from the Firebase token."""
    return AuthUserResponse(
        uid=current_user["uid"],
        email=current_user.get("email"),
        display_name=current_user.get("name"),
        photo_url=current_user.get("picture"),
        email_verified=bool(current_user.get("email_verified", False)),
    )


@app.post("/api/research/start", response_model=ResearchStatusResponse, tags=["research"])
async def start_research(
    payload: ResearchStartRequest,
    current_user: Dict[str, Any] = Depends(verify_token),
) -> ResearchStatusResponse:
    """Create a new research job placeholder owned by the authenticated user."""
    report_id = f"rpt_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    REPORT_STORE[report_id] = {
        "report_id": report_id,
        "user_id": current_user["uid"],
        "topic": payload.topic,
        "depth": payload.depth,
        "language": payload.language,
        "status": "pending",
        "current_agent": "orchestrator",
        "progress": 0,
        "confidence_score": 0,
        "source_credibility": [],
        "thinking_logs": [],
        "followup_questions": [],
        "report_markdown": "",
        "created_at": now,
        "completed_at": None,
    }
    return ResearchStatusResponse(report_id=report_id, status="pending", current_agent="orchestrator", progress=0)


@app.get("/api/research/{report_id}", response_model=ReportDataResponse, tags=["research"])
async def get_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(verify_token),
) -> ReportDataResponse:
    """Return a report only if it belongs to the authenticated user."""
    report = REPORT_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if report["user_id"] != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this report")
    return ReportDataResponse(**report)


@app.get("/api/reports/history", response_model=List[ResearchStatusResponse], tags=["research"])
async def get_history(current_user: Dict[str, Any] = Depends(verify_token)) -> List[ResearchStatusResponse]:
    """Return the current user's recent reports."""
    history: List[ResearchStatusResponse] = []
    for report in REPORT_STORE.values():
        if report["user_id"] != current_user["uid"]:
            continue
        history.append(
            ResearchStatusResponse(
                report_id=report["report_id"],
                status=report["status"],
                current_agent=report.get("current_agent"),
                progress=int(report.get("progress", 0)),
            )
        )
    return history


@app.delete("/api/reports/{report_id}", tags=["research"])
async def delete_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(verify_token),
) -> Dict[str, str]:
    """Delete a report only if it belongs to the current user."""
    report = REPORT_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if report["user_id"] != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to delete this report")
    del REPORT_STORE[report_id]
    return {"message": "Report deleted"}


@app.post("/api/export/pdf", tags=["export"])
async def export_pdf(
    payload: PDFExportRequest,
    current_user: Dict[str, Any] = Depends(verify_token),
) -> Dict[str, str]:
    """Return a placeholder PDF URL for the authenticated user's report."""
    report = REPORT_STORE.get(payload.report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if report["user_id"] != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to export this report")
    return {"pdf_url": f"/tmp/{payload.report_id}.pdf"}


@app.websocket("/ws/research/{report_id}")
async def research_websocket(websocket: WebSocket, report_id: str) -> None:
    """Stream placeholder live updates for a specific report id."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        from firebase_admin import auth as firebase_auth

        firebase_auth.verify_id_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await connect(report_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_json(WebSocketMessage(event="echo", report_id=report_id, message=message).dict())
    except WebSocketDisconnect:
        await disconnect(report_id, websocket)


# Placeholder agent routes keep the endpoint structure ready for the Day 5 orchestration layer.
@app.post("/api/agent/orchestrator", tags=["agents"])
async def orchestrator_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the orchestrator agent."""
    return {"status": "pending", "agent": "orchestrator", "user_id": current_user["uid"]}


@app.post("/api/agent/search", tags=["agents"])
async def search_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the search agent."""
    return {"status": "pending", "agent": "search", "user_id": current_user["uid"]}


@app.post("/api/agent/summary", tags=["agents"])
async def summary_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the summary agent."""
    return {"status": "pending", "agent": "summary", "user_id": current_user["uid"]}


@app.post("/api/agent/factcheck", tags=["agents"])
async def factcheck_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the fact-check agent."""
    return {"status": "pending", "agent": "factcheck", "user_id": current_user["uid"]}


@app.post("/api/agent/writer", tags=["agents"])
async def writer_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the writer agent."""
    return {"status": "pending", "agent": "writer", "user_id": current_user["uid"]}


@app.post("/api/agent/followup", tags=["agents"])
async def followup_placeholder(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Placeholder route for the follow-up agent."""
    return {"status": "pending", "agent": "followup", "user_id": current_user["uid"]}


app.openapi_tags = [
    {"name": "auth", "description": "Firebase login and current user endpoints"},
    {"name": "research", "description": "Research lifecycle endpoints"},
    {"name": "agents", "description": "Agent placeholders and orchestration hooks"},
    {"name": "export", "description": "PDF export endpoints"},
    {"name": "health", "description": "Health monitoring"},
]
