"""FastAPI application entry point for Multi-Agent Research Assistant.

This module coordinates authentications, background orchestration tasks,
multilingual document generations, health metrics, and WebSockets.
"""

from __future__ import annotations

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import (
    FastAPI, WebSocket, HTTPException,
    Depends, BackgroundTasks,
    WebSocketDisconnect, status
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize Firebase FIRST (before routes)
from utils.firebase_config import (
    initialize_firebase, get_firestore,
    get_storage
)

firebase_initialized = False
try:
    initialize_firebase()
    firebase_initialized = True
    logger.info("Firebase Admin successfully initialized on startup.")
except Exception as exc:
    logger.warning("Firebase Admin initialization failed on startup: %s. Proceeding in offline mode.", exc)

# Import auth
from utils.auth import (
    verify_token, save_user_to_firestore
)

# Import WebSocket manager
from utils.websocket_manager import ws_manager

# App Setup
app = FastAPI(
    title="Multi-Agent Research Assistant API",
    description="AI research pipeline with 6 agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Mappings
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]
if FRONTEND_URL:
    ALLOWED_ORIGINS.append(FRONTEND_URL)

# Add Vercel wildcard matching standard specs
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex="https://.*\\.vercel\\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# In-memory storage fallback keeps starter test suites functional when Firestore is offline.
REPORT_STORE: Dict[str, Dict[str, Any]] = {}


# --- PYDANTIC SCHEMAS ---

class ResearchRequest(BaseModel):
    """Payload to trigger new research run."""
    topic: str
    depth: str = "deep"
    language: str = "english"

    @validator("topic")
    def topic_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Topic cannot be empty")
        if len(v) > 500:
            raise ValueError("Topic too long (max 500 chars)")
        return v

    @validator("depth")
    def depth_valid(cls, v):
        allowed = ["quick", "deep", "expert"]
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"Depth must be one of {allowed}")
        return v

    @validator("language")
    def language_valid(cls, v):
        from utils.translator import validate_language
        return validate_language(v)


class LoginRequest(BaseModel):
    """User authentication payload containing client-side ID Token."""
    token: Optional[str] = None
    id_token: Optional[str] = None


class ExportPdfRequest(BaseModel):
    """Request to export report to printable PDF."""
    report_id: str


class ResearchStartResponse(BaseModel):
    """Synchronous creation response."""
    success: bool
    report_id: str
    topic: str
    status: str
    websocket_url: str
    message: str


class ReportResponse(BaseModel):
    """Detailed report payload metadata."""
    report_id: str
    topic: str
    depth: str
    language: str
    status: str
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None
    confidence_score: int
    pdf_url: Optional[str] = None
    followup_questions: Optional[List[str]] = None
    error: Optional[str] = None


class HistoryItem(BaseModel):
    """Summary of a past report for history dashboard."""
    report_id: str
    topic: str
    status: str
    created_at: Optional[str] = None
    confidence_score: int
    pdf_url: Optional[str] = None
    word_count: Optional[int] = None
    depth: str = "deep"
    language: str = "english"


# --- HELPERS ---

def generate_report_id() -> str:
    """Returns a short unique ID (first 8 chars of UUID)."""
    return str(uuid.uuid4())[:8]


def format_timestamp(ts: Any) -> Optional[str]:
    """Safely converts Firestore datetime types to ISO format string."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    try:
        return ts.isoformat()
    except Exception:
        return str(ts)


def firestore_doc_to_response(doc_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Converts a database doc dictionary to match the ReportResponse structure."""
    return {
        "report_id": doc_id,
        "topic": data.get("topic", ""),
        "depth": data.get("depth", "deep"),
        "language": data.get("language", "english"),
        "status": data.get("status", "pending"),
        "created_at": format_timestamp(data.get("createdAt")),
        "completed_at": format_timestamp(data.get("completedAt")),
        "report_data": data.get("reportData", {}),
        "confidence_score": data.get("confidenceScore", 0),
        "pdf_url": data.get("pdfUrl"),
        "followup_questions": data.get("followupQuestions", []),
        "error": data.get("error")
    }


# --- BACKGROUND COORDINATOR ---

async def run_pipeline_background(
    report_id: str,
    topic: str,
    depth: str,
    language: str,
    user_id: str
) -> None:
    """Executes the complete orchestration pipeline in the background.

    Defensively catches all exceptions to prevent task crashes and updates Firestore.
    """
    try:
        logger.info(f"Background pipeline starting: {report_id}")

        # 1. Update status to running
        try:
            db = get_firestore()
            db.collection("reports").document(report_id).update({"status": "running"})
        except Exception as fe:
            logger.warning("Could not set status to running in Firestore: %s", fe)

        # Update local store for offline fallbacks
        if report_id in REPORT_STORE:
            REPORT_STORE[report_id]["status"] = "running"
            REPORT_STORE[report_id]["current_agent"] = "orchestrator"

        # 2. Run the complete pipeline
        from agents.orchestrator import start_research
        final_state = await start_research(
            report_id=report_id,
            topic=topic,
            depth=depth,
            language=language,
            user_id=user_id
        )

        # 3. Retrieve final metrics
        final_report = final_state.get_field("final_report", {}) or {}
        confidence = final_state.get_field("confidence_score", 0)
        followup = final_state.get_field("followup_questions", []) or []
        status_val = final_state.get_field("status", "done")
        error_msg = final_state.get_field("error")

        # 4. Save results back to Firestore
        update_data = {
            "status": status_val,
            "reportData": final_report,
            "confidenceScore": confidence,
            "followupQuestions": followup
        }
        if status_val == "done":
            update_data["completedAt"] = datetime.now(timezone.utc)
        if error_msg:
            update_data["error"] = error_msg

        try:
            db = get_firestore()
            db.collection("reports").document(report_id).update(update_data)
        except Exception as fe:
            logger.warning("Could not save final research fields to Firestore: %s", fe)

        # Sync local store fallback
        if report_id in REPORT_STORE:
            REPORT_STORE[report_id].update({
                "status": status_val,
                "current_agent": final_state.get_field("current_agent"),
                "confidence_score": confidence,
                "thinking_logs": final_state.get_field("thinking_logs") or [],
                "followup_questions": followup,
                "report_data": final_report,
                "report_markdown": final_report.get("executive_summary", "") if isinstance(final_report, dict) else "",
                "completed_at": datetime.now(timezone.utc).isoformat() if status_val == "done" else None,
                "error": error_msg
            })

        logger.info(f"Pipeline complete for report {report_id}: status={status_val}")

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"Background research pipeline failed for report {report_id}: {error_msg}", exc_info=True)

        # Record failure in Firestore
        try:
            db = get_firestore()
            db.collection("reports").document(report_id).update({
                "status": "failed",
                "error": error_msg
            })
        except Exception as fe:
            logger.error("Could not record pipeline failure in Firestore: %s", fe)

        # Record failure locally
        if report_id in REPORT_STORE:
            REPORT_STORE[report_id].update({
                "status": "failed",
                "error": error_msg
            })

        # Alert listeners
        try:
            await ws_manager.emit_error(report_id, "system", f"Pipeline failed: {error_msg}")
        except Exception as ws_err:
            logger.warning("Could not emit background error event over WebSockets: %s", ws_err)


# --- ROUTE ENDPOINTS ---

@app.get("/", tags=["health"])
async def root_health() -> Dict[str, Any]:
    """Lightweight welcome and routing layout health check."""
    return {
        "status": "running",
        "project": "Multi-Agent Research Assistant",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "research": "POST /api/research/start",
            "status": "GET /api/research/{id}",
            "history": "GET /api/reports/history",
            "pdf": "POST /api/export/pdf",
            "websocket": "WS /ws/research/{id}"
        }
    }


@app.get("/api/health/all", tags=["health"])
async def health_all() -> Dict[str, Any]:
    """Consolidated connectivity check of all third-party services."""
    services: Dict[str, Dict[str, Any]] = {}
    is_firebase_ok = True

    # 1. Pinecone
    try:
        from tools.pinecone_tool import get_index_stats
        stats = get_index_stats()
        services["pinecone"] = {
            "status": "healthy" if stats.get("status") != "error" else "error",
            "total_vectors": stats.get("total_vectors", 0)
        }
    except Exception as exc:
        services["pinecone"] = {"status": "error", "message": str(exc)}

    # 2. Tavily
    try:
        from tools.tavily_tool import initialize_tavily
        client = initialize_tavily()
        services["tavily"] = {"status": "healthy" if client else "error"}
    except Exception as exc:
        services["tavily"] = {"status": "error", "message": str(exc)}

    # 3. Firebase Firestore
    if firebase_initialized:
        try:
            db = get_firestore()
            # Query collection test
            db.collection("reports").limit(1).get()
            services["firebase"] = {"status": "healthy"}
        except Exception as exc:
            is_firebase_ok = False
            services["firebase"] = {"status": "error", "message": str(exc)}
    else:
        is_firebase_ok = False
        services["firebase"] = {
            "status": "error",
            "message": "Firebase Admin not initialized (offline fallback mode)"
        }

    # 4. OpenAI API Key check
    api_key = os.getenv("OPENAI_API_KEY")
    services["openai"] = {
        "status": "configured" if api_key and api_key.strip() else "missing"
    }

    # 5. WebSockets Manager status
    services["websocket"] = {
        "status": "healthy",
        "active_connections": ws_manager.get_connected_count()
    }

    # Decide consolidated status
    if not is_firebase_ok:
        overall = "down"
    elif any(s["status"] == "error" for s in services.values()):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health/pinecone", tags=["health"])
async def health_pinecone() -> Dict[str, Any]:
    """Return Pinecone index stats and connection metrics."""
    try:
        from tools.pinecone_tool import get_index_stats
        stats = get_index_stats()
        return {
            "service": "pinecone",
            "status": "healthy" if stats.get("status") != "error" else "error",
            "stats": stats
        }
    except Exception as exc:
        return {"service": "pinecone", "status": "error", "message": str(exc)}


@app.get("/api/health/tavily", tags=["health"])
async def health_tavily() -> Dict[str, Any]:
    """Return Tavily Search API connectivity status."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"service": "tavily", "status": "error", "message": "TAVILY_API_KEY is not configured"}
    try:
        from tools.tavily_tool import search
        results = search("test query", max_results=1)
        return {"service": "tavily", "status": "healthy", "results_count": len(results)}
    except Exception as exc:
        return {"service": "tavily", "status": "error", "message": str(exc)}


@app.get("/api/health/websocket", tags=["health"])
async def health_websocket() -> Dict[str, Any]:
    """Return active connection statistics inside WebSocketManager."""
    stats = ws_manager.get_connection_stats()
    return {
        "status": "healthy",
        "active_connections": stats["active_connections"],
        "reports_with_history": stats["reports_with_history"],
        "connections": stats["connections"]
    }


@app.get("/api/languages", tags=["localization"])
async def get_languages() -> Dict[str, Any]:
    """Return configured translator language details."""
    from utils.translator import get_all_languages
    return {
        "languages": get_all_languages(),
        "default": "english"
    }


@app.post("/api/auth/login", tags=["auth"])
async def login_user(payload: LoginRequest) -> Dict[str, Any]:
    """Verify bearer token credentials with Firebase Admin and register user document."""
    try:
        from firebase_admin import auth as firebase_auth
        token_val = payload.token or payload.id_token
        if not token_val:
            raise HTTPException(status_code=400, detail="Token payload not provided")
        decoded = firebase_auth.verify_id_token(token_val)
        user = {
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "name": decoded.get("name") or decoded.get("email", "").split("@")[0],
            "picture": decoded.get("picture"),
            "email_verified": decoded.get("email_verified", False),
        }
        saved_user = save_user_to_firestore(user)
        return {
            "success": True,
            "user": {
                "uid": saved_user["uid"],
                "email": saved_user.get("email"),
                "name": saved_user.get("displayName"),
                "picture": saved_user.get("photoURL"),
            },
            "message": "Login successful"
        }
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify Firebase auth token"
        )


@app.get("/api/auth/me", tags=["auth"])
async def get_me(current_user: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """Retrieves validated token credentials representing active user profile."""
    return {
        "uid": current_user["uid"],
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "picture": current_user.get("picture")
    }


@app.post("/api/research/start", response_model=ResearchStartResponse, tags=["research"])
async def start_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Synchronously creates a research document and triggers background agent tasks.

    MUST return control to client in under 1 second.
    """
    try:
        topic = request.topic.strip()
        depth = request.depth
        language = request.language
        user_id = current_user["uid"]

        report_id = generate_report_id()

        # 1. Create document in Firestore
        doc_data = {
            "userId": user_id,
            "topic": topic,
            "depth": depth,
            "language": language,
            "status": "pending",
            "createdAt": datetime.now(timezone.utc),
            "completedAt": None,
            "reportData": {},
            "confidenceScore": 0,
            "pdfUrl": None,
            "error": None,
            "followupQuestions": []
        }

        try:
            db = get_firestore()
            db.collection("reports").document(report_id).set(doc_data)
        except Exception as fe:
            logger.warning("Could not set pending report in Firestore: %s", fe)

        # 2. Store locally in memory for fallback tests
        REPORT_STORE[report_id] = {
            "report_id": report_id,
            "user_id": user_id,
            "topic": topic,
            "depth": depth,
            "language": language,
            "status": "pending",
            "current_agent": "orchestrator",
            "progress": 0,
            "confidence_score": 0,
            "thinking_logs": [],
            "followup_questions": [],
            "report_data": {},
            "report_markdown": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "pdf_url": None,
            "error": None
        }

        # 3. Run orchestrator agents pipeline in background
        background_tasks.add_task(
            run_pipeline_background,
            report_id=report_id,
            topic=topic,
            depth=depth,
            language=language,
            user_id=user_id
        )

        logger.info(f"Research pipeline successfully triggered for topic: '{topic[:40]}...' ID: {report_id}")

        return {
            "success": True,
            "report_id": report_id,
            "topic": topic,
            "status": "pending",
            "websocket_url": f"/ws/research/{report_id}",
            "message": "Research pipeline started"
        }

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error("Failed to start research task: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate research workflow"
        )


@app.get("/api/research/{report_id}", response_model=ReportResponse, tags=["research"])
async def get_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Retrieves document matching ID, verifying ownership."""
    report_data = None

    # Try Firestore
    try:
        db = get_firestore()
        doc = db.collection("reports").document(report_id).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("userId") != current_user["uid"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this report"
                )
            return firestore_doc_to_response(report_id, data)
    except HTTPException:
        raise
    except Exception as fe:
        logger.warning("Firestore report fetch failed, using local store: %s", fe)

    # Fallback to local store
    local_report = REPORT_STORE.get(report_id)
    if not local_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    if local_report.get("user_id") != current_user["uid"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this report"
        )

    # Map local response structure
    return {
        "report_id": report_id,
        "topic": local_report.get("topic", ""),
        "depth": local_report.get("depth", "deep"),
        "language": local_report.get("language", "english"),
        "status": local_report.get("status", "pending"),
        "created_at": format_timestamp(local_report.get("created_at")),
        "completed_at": format_timestamp(local_report.get("completed_at")),
        "report_data": local_report.get("report_data", {}),
        "confidence_score": local_report.get("confidence_score", 0),
        "pdf_url": local_report.get("pdf_url"),
        "followup_questions": local_report.get("followup_questions", []),
        "error": local_report.get("error")
    }


@app.get("/api/reports/history", tags=["research"])
async def get_history(
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Retrieves past research history associated with authenticated profile ID."""
    db_history = []
    limit = min(max(1, limit), 50)
    is_db_success = False

    # Try Firestore
    try:
        db = get_firestore()
        reports_ref = db.collection("reports")\
            .where("userId", "==", current_user["uid"])\
            .order_by("createdAt", direction="DESCENDING")\
            .limit(limit)

        docs = reports_ref.stream()
        for doc in docs:
            data = doc.to_dict()
            report_data = data.get("reportData", {})
            db_history.append({
                "report_id": doc.id,
                "topic": data.get("topic", ""),
                "status": data.get("status", "unknown"),
                "created_at": format_timestamp(data.get("createdAt")),
                "confidence_score": data.get("confidenceScore", 0),
                "pdf_url": data.get("pdfUrl"),
                "word_count": report_data.get("word_count"),
                "depth": data.get("depth", "deep"),
                "language": data.get("language", "english")
            })
        is_db_success = True
    except Exception as fe:
        logger.warning("Firestore query failed for report history: %s", fe)

    # Fallback to local store filtering
    if not is_db_success:
        local_history = []
        for rid, report in REPORT_STORE.items():
            if report.get("user_id") == current_user["uid"]:
                rep_data = report.get("report_data", {})
                local_history.append({
                    "report_id": rid,
                    "topic": report.get("topic", ""),
                    "status": report.get("status", "unknown"),
                    "created_at": format_timestamp(report.get("created_at")),
                    "confidence_score": report.get("confidence_score", 0),
                    "pdf_url": report.get("pdf_url"),
                    "word_count": rep_data.get("word_count"),
                    "depth": report.get("depth", "deep"),
                    "language": report.get("language", "english")
                })
        # Sort newest first
        local_history.sort(key=lambda x: x["created_at"] or "", reverse=True)
        db_history = local_history[:limit]

    return {
        "success": True,
        "reports": db_history,
        "count": len(db_history)
    }


@app.delete("/api/reports/{report_id}", tags=["research"])
async def delete_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Deletes research records, executing cleanups in Pinecone and Storage."""
    try:
        report_data = None
        has_firestore_doc = False

        # Fetch doc first for ownership verification
        try:
            db = get_firestore()
            doc_ref = db.collection("reports").document(report_id)
            doc = doc_ref.get()
            if doc.exists:
                report_data = doc.to_dict()
                has_firestore_doc = True
                if report_data.get("userId") != current_user["uid"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to delete this report"
                    )
        except HTTPException:
            raise
        except Exception as fe:
            logger.warning("Firestore fetch failed during delete check, using local store fallback: %s", fe)

        # Fallback to local store checks
        if not report_data:
            local_report = REPORT_STORE.get(report_id)
            if not local_report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found"
                )
            if local_report.get("user_id") != current_user["uid"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this report"
                )
            report_data = local_report

        # 1. Clean up Pinecone vectors
        try:
            from tools.pinecone_tool import delete_report_chunks
            delete_report_chunks(report_id)
        except Exception as exc:
            logger.warning("Pinecone vector deletion failed for report %s: %s", report_id, exc)

        # 2. Clean up Firebase Storage PDF
        pdf_url = report_data.get("pdfUrl") or report_data.get("pdf_url")
        if pdf_url:
            try:
                bucket = get_storage()
                blob = bucket.blob(f"reports/{report_id}.pdf")
                if blob.exists():
                    blob.delete()
            except Exception as exc:
                logger.warning("Firebase Storage deletion failed for report %s.pdf: %s", report_id, exc)

        # 3. Clean up database entry
        if has_firestore_doc:
            try:
                db = get_firestore()
                db.collection("reports").document(report_id).delete()
            except Exception as fe:
                logger.warning("Could not delete report document in Firestore: %s", fe)

        # Clean up local store fallback
        if report_id in REPORT_STORE:
            del REPORT_STORE[report_id]

        logger.info(f"Report ID {report_id} successfully deleted by user: {current_user['uid']}")

        return {
            "success": True,
            "message": "Report deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Delete report endpoint failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete report"
        )


@app.post("/api/export/pdf", tags=["export"])
async def export_pdf(
    payload: ExportPdfRequest,
    current_user: Dict[str, Any] = Depends(verify_token),
) -> Dict[str, Any]:
    """Generates PDF from a completed report and uploads to Firebase Storage."""
    try:
        report_data = None
        topic = ""
        report_id = payload.report_id

        # Try Firestore
        try:
            db = get_firestore()
            doc_ref = db.collection("reports").document(report_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("userId") != current_user["uid"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to access this report"
                    )
                report_data = data.get("reportData", {})
                topic = data.get("topic", "")
        except HTTPException:
            raise
        except Exception as fe:
            logger.warning("Firestore lookup failed, falling back to local REPORT_STORE: %s", fe)

        # Fallback to local store
        if not report_data:
            local_report = REPORT_STORE.get(report_id)
            if not local_report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found"
                )
            if local_report.get("user_id") != current_user["uid"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this report"
                )
            topic = local_report.get("topic", "")
            report_data = local_report.get("final_report") or local_report

        if not report_data or (isinstance(report_data, dict) and not report_data.get("executive_summary")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report not yet complete"
            )

        from tools.pdf_export import generate_and_upload_pdf

        # Generate and upload PDF
        result = generate_and_upload_pdf(
            report=report_data,
            topic=topic,
            report_id=report_id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF generation failed: {result.get('error')}"
            )

        # Save URL back to Firestore
        try:
            db = get_firestore()
            db.collection("reports").document(report_id).update({
                "pdfUrl": result["pdf_url"]
            })
        except Exception as fe:
            logger.warning("Could not update pdfUrl in Firestore: %s", fe)

        # Update in-memory store
        if report_id in REPORT_STORE:
            REPORT_STORE[report_id]["pdf_url"] = result["pdf_url"]

        return {
            "success": True,
            "pdf_url": result["pdf_url"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("PDF export endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/health/pdf", tags=["health"])
async def pdf_health() -> Dict[str, Any]:
    """Return Devanagari Unicode PDF font registration status."""
    try:
        from tools.pdf_export import register_fonts
        unicode_ok = register_fonts()
        return {
            "status": "healthy",
            "unicode_font_available": unicode_ok
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# --- WEBSOCKET CHANNELS ---

@app.websocket("/ws/research/{report_id}")
async def websocket_endpoint(websocket: WebSocket, report_id: str) -> None:
    """Streams live research milestones, supporting ping/pong keep-alives, history playback, and disconnects."""
    await ws_manager.connect(websocket, report_id)
    try:
        while True:
            try:
                # Wait for keep-alive packets or client events
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "history":
                    # Client requesting event history manually
                    history = ws_manager.get_event_history(report_id)
                    await websocket.send_json({
                        "event": "history",
                        "agent": "system",
                        "message": f"{len(history)} events",
                        "data": {"events": history},
                        "timestamp": int(time.time() * 1000)
                    })
            except asyncio.TimeoutError:
                # Dispatch keepalive ping to check connections
                try:
                    await websocket.send_json({
                        "event": "keepalive",
                        "agent": "system",
                        "message": "ping",
                        "data": {},
                        "timestamp": int(time.time() * 1000)
                    })
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected: {report_id}")
    except Exception as exc:
        logger.error(f"WS error for report {report_id}: {exc}")
    finally:
        await ws_manager.disconnect(report_id)
