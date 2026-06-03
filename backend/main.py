"""FastAPI main application for Multi-Agent Research Assistant
This module provides:
- FastAPI app with CORS and OpenAPI metadata
- Pydantic request/response models used by the agents
- Placeholder HTTP endpoints for the 6 agents
- WebSocket endpoint to stream live agent events

Replace placeholder logic with real agent implementations
when wiring to LangChain / background tasks.
"""

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables from .env at startup
load_dotenv()

API_TITLE = "Multi-Agent Research Assistant"
API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "Orchestrates multiple cooperating agents to produce a fully-cited, verified research report."
)

app = FastAPI(title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION)

# CORS configuration - expand origins for production (use env var)
origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# Pydantic models (requests/responses)
# ---------------------------

class ResearchStartRequest(BaseModel):
    topic: str = Field(..., description="Research topic string")
    depth: str = Field("deep", description="quick | deep | expert")
    language: str = Field("english", description="english | hindi | spanish")
    user_id: Optional[str] = Field(None, description="Firebase user id")


class ResearchStatusResponse(BaseModel):
    report_id: str
    status: str
    current_agent: Optional[str]
    progress: Optional[int] = 0


class SubQuestionsRequest(BaseModel):
    topic: str
    depth: Optional[str] = "deep"


class SubQuestionsResponse(BaseModel):
    report_id: Optional[str]
    sub_questions: List[str]


class SearchRequest(BaseModel):
    report_id: str
    sub_questions: List[str]


class SearchResultItem(BaseModel):
    url: str
    title: Optional[str]
    snippet: Optional[str]
    credibility: Optional[str] = Field(None, description="Academic | News | Blog | Unknown")


class SearchResponse(BaseModel):
    report_id: str
    results: Dict[str, List[SearchResultItem]]


class SummaryItem(BaseModel):
    sub_question: str
    summary: str
    citations: List[SearchResultItem]


class SummariesResponse(BaseModel):
    report_id: str
    summaries: List[SummaryItem]


class ClaimItem(BaseModel):
    claim: str
    label: str = Field(..., description="verified | uncertain | unverified")
    confidence: int = Field(..., ge=0, le=100)
    supporting_sources: List[SearchResultItem]


class VerifiedClaimsResponse(BaseModel):
    report_id: str
    claims: List[ClaimItem]


class FinalReportRequest(BaseModel):
    report_id: str
    topic: str
    language: Optional[str] = "english"


class FinalReportResponse(BaseModel):
    report_id: str
    title: str
    markdown: str
    confidence_score: int
    source_credibility: Dict[str, str]


class FollowUpResponse(BaseModel):
    report_id: str
    followup_questions: List[str]


# Agent state model for storage / Firestore
class AgentState(BaseModel):
    report_id: str
    topic: str
    depth: str
    language: str
    user_id: Optional[str]
    sub_questions: List[str] = []
    search_results: Dict[str, List[Dict[str, Any]]] = {}
    summaries: List[Dict[str, Any]] = []
    verified_claims: List[Dict[str, Any]] = []
    final_report: Optional[Dict[str, Any]] = None
    followup_questions: List[str] = []
    confidence_score: int = 0
    source_credibility: Dict[str, str] = {}
    thinking_logs: List[Dict[str, Any]] = []
    status: str = "pending"
    current_agent: Optional[str] = None


# In-memory store for demo (replace with Firestore in production)
IN_MEMORY_REPORTS: Dict[str, Dict[str, Any]] = {}


# WebSocket connection manager (simple helper functions)
from .utils.websocket_manager import connect, disconnect, broadcast


# ---------------------------
# API Endpoints
# ---------------------------


@app.post("/api/research/start", response_model=ResearchStatusResponse, tags=["research"])
async def start_research(payload: ResearchStartRequest, background_tasks: BackgroundTasks):
    """Start the multi-agent research workflow.
    Creates a `report_id`, initializes `AgentState`, and enqueues background tasks
    (background task wiring is placeholder — implement orchestration with Celery / BackgroundTasks / Cloud Tasks).
    """
    report_id = f"rpt_{int(datetime.utcnow().timestamp())}"
    state = AgentState(
        report_id=report_id,
        topic=payload.topic,
        depth=payload.depth,
        language=payload.language,
        user_id=payload.user_id,
        status="pending",
        current_agent="orchestrator",
    )
    IN_MEMORY_REPORTS[report_id] = state.dict()

    # TODO: schedule background orchestration that runs the 6 agents in sequence

    return ResearchStatusResponse(report_id=report_id, status="pending", current_agent="orchestrator", progress=0)


@app.post("/api/agent/orchestrator", response_model=SubQuestionsResponse, tags=["agents"])
async def orchestrator(req: SubQuestionsRequest):
    """Generates sub-questions for a topic based on `depth`.
    Placeholder uses simple heuristics; replace with GPT-4o calls.
    """
    # Simple placeholder splitting - replace with real LLM prompt
    base = req.topic.strip()
    sub_questions = [f"What is the history of {base}?", f"What are the current challenges in {base}?", f"What are future directions for {base}?"]
    return SubQuestionsResponse(report_id=None, sub_questions=sub_questions)


@app.post("/api/agent/search", response_model=SearchResponse, tags=["agents"])
async def search_agent(req: SearchRequest):
    """Searches the web for each sub-question using Tavily (placeholder).
    Returns a mapping sub_question -> list of `SearchResultItem` with credibility tagging.
    """
    results: Dict[str, List[SearchResultItem]] = {}
    for sq in req.sub_questions:
        # Placeholder single synthetic result
        item = SearchResultItem(url="https://example.com", title=f"Result for: {sq}", snippet="Snippet...", credibility="Unknown")
        results[sq] = [item]
    return SearchResponse(report_id=req.report_id, results=results)


@app.post("/api/agent/summary", response_model=SummariesResponse, tags=["agents"])
async def summary_agent(req: SearchRequest):
    """Summarizes search results for each sub-question using RAG.
    Placeholder: returns short summaries referencing the first result.
    """
    summaries: List[SummaryItem] = []
    for sq in req.sub_questions:
        summaries.append(SummaryItem(sub_question=sq, summary=f"Short summary for {sq}", citations=[]))
    return SummariesResponse(report_id=req.report_id, summaries=summaries)


@app.post("/api/agent/factcheck", response_model=VerifiedClaimsResponse, tags=["agents"])
async def factcheck_agent(req: SummariesResponse):
    """Extracts claims and cross verifies across sources.
    Placeholder: marks everything as 'uncertain' with 50% confidence.
    """
    claims: List[ClaimItem] = []
    for s in req.summaries:
        claims.append(ClaimItem(claim=f"Claim from {s.sub_question}", label="uncertain", confidence=50, supporting_sources=[]))
    return VerifiedClaimsResponse(report_id=req.report_id, claims=claims)


@app.post("/api/agent/writer", response_model=FinalReportResponse, tags=["agents"])
async def writer_agent(req: FinalReportRequest):
    """Composes the final report in markdown with inline citations and computes confidence score.
    Placeholder: returns a simple markdown document.
    """
    markdown = f"# {req.topic}\n\nThis is a starter report for {req.topic}. Replace with real generated content."
    return FinalReportResponse(report_id=req.report_id, title=req.topic, markdown=markdown, confidence_score=60, source_credibility={})


@app.post("/api/agent/followup", response_model=FollowUpResponse, tags=["agents"])
async def followup_agent(req: FinalReportRequest):
    """Suggests follow-up research questions based on the final report.
    Placeholder returns three follow-up items.
    """
    followups = [f"Deep dive into methodology for {req.topic}", f"Compare {req.topic} across regions", f"Investigate ethical implications of {req.topic}"]
    return FollowUpResponse(report_id=req.report_id, followup_questions=followups)


@app.post("/api/export/pdf")
async def export_pdf_endpoint(req: Dict[str, str]):
    """Generate PDF for a report. Returns URL to the generated PDF.
    Placeholder implements a call into `tools.pdf_export`.
    """
    report_id = req.get("report_id")
    rpt = IN_MEMORY_REPORTS.get(report_id)
    if not rpt or not rpt.get("final_report"):
        raise HTTPException(status_code=404, detail="Report not found or not ready")

    from .tools.pdf_export import export_pdf
    out_path = os.path.abspath(f"./tmp/{report_id}.pdf")
    # Ensure directory exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    export_pdf(rpt.get("final_report",""), out_path)
    return {"pdf_url": f"file://{out_path}"}


@app.get("/api/research/{report_id}", response_model=AgentState, tags=["research"])
async def get_report(report_id: str):
    """Fetch the full agent state for a report_id. In production, pull from Firestore.
    """
    r = IN_MEMORY_REPORTS.get(report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return AgentState(**r)


@app.get("/api/reports/history", response_model=List[ResearchStatusResponse], tags=["research"])
async def reports_history(user_id: Optional[str] = None):
    """Return a list of recent reports. Filter by user_id when provided.
    For starter code this returns in-memory entries.
    """
    out: List[ResearchStatusResponse] = []
    for rid, v in IN_MEMORY_REPORTS.items():
        if user_id and v.get("user_id") != user_id:
            continue
        out.append(ResearchStatusResponse(report_id=rid, status=v.get("status","pending"), current_agent=v.get("current_agent"), progress=0))
    return out


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    """Delete a report and associated agent logs/storage. Placeholder removes from in-memory store."""
    if report_id in IN_MEMORY_REPORTS:
        del IN_MEMORY_REPORTS[report_id]
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Report not found")


@app.get("/healthz", tags=["health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# WebSocket endpoint for live agent updates
@app.websocket("/ws/research/{report_id}")
async def websocket_endpoint(websocket: WebSocket, report_id: str):
    """Accepts websocket connections and streams agent events for a report_id.
    Clients should connect to `/ws/research/{report_id}` to receive JSON events
    in the shape described in the project spec (agent_start, agent_update, etc.).
    """
    await connect(report_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo for now; real implementation will push agent events from background tasks
            await websocket.send_json({"event": "echo", "message": data})
    except WebSocketDisconnect:
        await disconnect(report_id, websocket)


# OpenAPI tags
app.openapi_tags = [
    {"name": "research", "description": "Start and manage research reports"},
    {"name": "agents", "description": "Individual agent endpoints (orchestrator, search, summary, factcheck, writer, followup)"},
    {"name": "export", "description": "PDF export and utilities"},
    {"name": "health", "description": "Health checks"},
]


# To run locally: `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
