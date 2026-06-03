# Multi-Agent Research Assistant

A Multi-Agent Research Assistant that converts a user-provided research topic into a fully-cited, verified research report with PDF export.

<!-- Badges (replace with real links when available) -->
- Build: ![build](https://img.shields.io/badge/build-pending-lightgrey)
- License: ![license](https://img.shields.io/badge/license-MIT-blue)

## Highlights / Unique Features
- **Confidence Score**: 0-100% report-level confidence computed from cross-source corroboration.
- **Source Credibility Rating**: Classifies sources as Academic / News / Blog / Unknown.
- **Smart Follow-up Questions**: Suggests next research directions after each report.
- **Agent Thinking Logs**: Transparent per-agent reasoning and intermediate steps.
- **Multi-Language Output**: Supports English, Hindi, Spanish outputs.
- **Research Comparison Mode**: Side-by-side comparison of two topics.

## Tech Stack
- Backend: Python 3.11, FastAPI, LangChain (agents), OpenAI (GPT-4o), Pinecone, Firebase Admin SDK, ReportLab
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, Framer Motion
- Dev / Infra: Docker, Docker Compose; Deploy: GCP Cloud Run (backend), Vercel (frontend)

## Folder Structure
```
multi-agent-research/
├── backend/                # FastAPI app, agents, tools, memory
├── frontend/               # Next.js app (App Router) and React components
├── .env                    # Environment template (do not commit secrets)
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Quick Local Setup (developer-friendly)

1. Clone the repository and change into project root:

```bash
git clone <repo-url>
cd multi-agent-research
```

2. Backend (Python): create and activate virtualenv, install packages:

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Mac/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

3. Frontend (Next.js): see `frontend/` or create app with `npx` (instructions below).

4. Copy `.env` and fill real secret values:

```bash
cp .env.example .env    # or edit .env directly
```

5. Start services (development):

```bash
docker-compose up --build
# or run backend and frontend separately during development
```

## Environment Variables (summary)
See `.env` at project root for a complete template. Key variables:

- `OPENAI_API_KEY`: OpenAI API key (required)
- `TAVILY_API_KEY`: Tavily web-search API key (used by Search Agent)
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`: Pinecone credentials for embeddings
- `FIREBASE_SERVICE_ACCOUNT`: Path to Firebase service account JSON
- `PDF_OUTPUT_PATH`: Local path for generated PDFs (development)

## API Endpoints (starter)
All endpoints are prefixed with `/api` and are implemented in `backend/main.py`.

- `POST /api/research/start` — Start a research run (body: `topic`, `depth`, `language`)
- `GET /api/research/{report_id}` — Retrieve full agent state / report
- `GET /api/reports/history` — List recent reports
- `DELETE /api/reports/{report_id}` — Delete a report
- `POST /api/agent/orchestrator` — (internal) generate sub-questions
- `POST /api/agent/search` — (internal) run web search for sub-questions
- `POST /api/agent/summary` — (internal) produce RAG summaries
- `POST /api/agent/factcheck` — (internal) verify claims
- `POST /api/agent/writer` — (internal) compose final report
- `POST /api/agent/followup` — (internal) suggest follow-up questions
- `POST /api/export/pdf` — Generate PDF for a report
- `WS  /ws/research/{report_id}` — WebSocket for live agent events

## What to check after setup
- Backend: visit `http://localhost:8000/docs` for OpenAPI UI.
- Health: `GET http://localhost:8000/healthz` should return `{"status":"ok"}`.
- Frontend: `http://localhost:3000` (if running) should load Next.js app.

## Coming Soon
- Production-ready PDF styling and export to Firebase Storage
- Full LangChain orchestration and Pinecone-backed RAG
- Authentication, quotas, and deployment pipeline

## License
MIT (placeholder)

