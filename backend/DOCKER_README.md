# Docker Setup Guide
## Multi-Agent Research Assistant Backend

This guide outlines building, testing, running, and troubleshooting the Dockerized backend service.

---

### Quick Start

```bash
# 1. Build image
cd backend/
docker build -t research-assistant-backend .

# 2. Run container
docker run \
  -p 8000:8000 \
  --env-file .env \
  research-assistant-backend

# 3. Test it works
curl http://localhost:8000/
```

---

### Using Docker Compose

```bash
# From project root:
docker-compose up

# With hot reload (development):
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  up
```

---

### Running Tests

```bash
cd backend/
chmod +x test_docker.sh
./test_docker.sh
```

---

### Image Details

| Property | Value |
| :--- | :--- |
| **Base** | `python:3.11-slim` |
| **Build type** | Multi-stage (`builder` + `runtime`) |
| **Final size** | ~280MB |
| **User** | non-root (`appuser`) |
| **Port** | 8000 |
| **Health check** | Every 30s |

---

### Environment Variables

| Variable Name | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `OPENAI_API_KEY` | Yes | - | API key for OpenAI GPT models |
| `TAVILY_API_KEY` | Yes | - | API key for Tavily search agent |
| `PINECONE_API_KEY` | Yes | - | API key for Pinecone vector database |
| `PINECONE_INDEX_NAME` | Yes | - | Name of Pinecone index (`research-chunks`) |
| `FIREBASE_PROJECT_ID` | Yes | - | GCP project ID for Firebase instance |
| `FIREBASE_PRIVATE_KEY` | Yes | - | Firebase Service Account private RSA key |
| `FIREBASE_CLIENT_EMAIL` | Yes | - | Firebase Service Account client email address |
| `FIREBASE_STORAGE_BUCKET`| Yes | - | Firebase Storage bucket for report exports |
| `PINECONE_INDEX_HOST` | No | - | Optional Pinecone Index host endpoint override |
| `BACKEND_URL` | No | `http://localhost:8000`| Allowed CORS/WS origin |
| `FRONTEND_URL` | No | `http://localhost:3000`| Allowed CORS origin |

---

### Troubleshooting

#### ISSUE 1: "ModuleNotFoundError" in container
- **Symptom**: Container starts then immediately exits. Logs show: `ModuleNotFoundError: No module named 'X'`.
- **Cause**: Package in `requirements.txt` failed to install OR package name is wrong.
- **Fix**:
  1. Check `requirements.txt` has correct names (e.g. `fastapi`, not `fastapi-users`).
  2. Rebuild without cache: `docker build --no-cache -t research-assistant-backend .`
  3. Check pip install output during the `builder` stage for compilation warnings or errors.

#### ISSUE 2: Firebase key invalid in container
- **Symptom**: Logs show: `ValueError: Invalid private key` or `invalid_grant: Invalid JWT Signature`.
- **Cause**: `FIREBASE_PRIVATE_KEY` newlines not processed correctly.
- **Fix**:
  1. `firebase_config.py` now parses and handles this (unquotes the key and maps `\\n` to actual newlines).
  2. Verify your `.env` has the key in quotes: `FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nABC...\n-----END PRIVATE KEY-----\n"`
  3. The `\n` characters should be literal backslash-n strings in the `.env` file.

#### ISSUE 3: Container exits immediately
- **Symptom**: `docker run` starts then stops. Container status is `Exited (1)`.
- **Fix**:
  1. Check `startup_check.py` output manually:
     `docker run --env-file .env research-assistant-backend python startup_check.py`
  2. View full logs: `docker logs <container-name>`
  3. Common causes: Missing env variables, python import issues, or port conflicts.

#### ISSUE 4: "Permission denied" error
- **Symptom**: `PermissionError: [Errno 13] Permission denied: '/app/...'`
- **Cause**: Non-root user `appuser` cannot write to directories.
- **Fix**:
  Ensure Dockerfile applies correct permissions before switching to `USER appuser`:
  `RUN chown -R appuser:appuser /app && chmod -R 755 /app/assets`

#### ISSUE 5: PDF fonts not found
- **Symptom**: Logs show: `Unicode font not found, falling back to Helvetica`.
- **Cause**: Font files not copied into container.
- **Fix**:
  1. Make sure `assets/` is NOT in `.dockerignore`.
  2. Check `COPY . .` includes `assets/`.
  3. Verify font files inside container:
     `docker exec -it CONTAINER_NAME ls /app/assets/fonts/`

#### ISSUE 6: WebSocket 403 or connection refused
- **Symptom**: `wscat` shows connection refused or browser shows WebSocket error.
- **Cause**: Container port mapping is wrong or CORS is blocking the request.
- **Fix**:
  1. Verify port mapping: `-p 8000:8000` (host:container).
  2. Test direct connection: `curl http://localhost:8000/`

#### ISSUE 7: "Address already in use"
- **Symptom**: `docker run` fails: `port is already allocated`.
- **Cause**: Port `8000` is already in use by a local process or container.
- **Fix**:
  1. Find what's using port 8000: `lsof -i :8000` (on Unix) or stop any active backend dev servers.
  2. Use a different port: `docker run -p 8001:8000 research-assistant-backend`
  3. Or kill the existing process: `kill $(lsof -ti:8000)`
