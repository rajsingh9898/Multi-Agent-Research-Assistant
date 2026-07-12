# ────────────────────────────────────────────────────────
# STAGE 1: builder
# The builder stage compiles C-extensions and gathers dependencies.
# Using a multi-stage build allows us to install compiling utilities (gcc, g++, dev headers) 
# and clean them up entirely so they do not bloat the final production runtime image.
# ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install system compilation dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Set up build directory
WORKDIR /build

# Copy only requirements specification to optimize layer caching
COPY requirements.txt .

# Install dependencies in user space to simplify copying to runtime stage
RUN pip install \
    --no-cache-dir \
    --user \
    --upgrade pip \
    -r requirements.txt


# ────────────────────────────────────────────────────────
# STAGE 2: runtime
# The runtime stage is the clean, minimal production container image.
# ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create a non-root group and user for security compliance (prevents container escape attacks)
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app appuser

# Install minimal system dependencies required at runtime
# - curl: needed for health checks in compose and monitoring
# - ca-certificates: required to execute secure HTTPS calls to third-party APIs (OpenAI, Tavily, Pinecone)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Set working directory for execution
WORKDIR /app

# Copy python dependencies from builder stage into the non-root user's home directory
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code and adjust ownership to the non-root user
COPY --chown=appuser:appuser . .

# Ensure the font assets directory exists and is owned by the appuser
RUN mkdir -p /app/assets/fonts && \
    chown -R appuser:appuser /app/assets && \
    chmod -R 755 /app/assets

# Switch execution context to the non-root user
USER appuser

# Set PATH to include local user binaries
ENV PATH=/home/appuser/.local/bin:$PATH

# Python execution behavior:
# - PYTHONUNBUFFERED: forces print outputs to stdout immediately without buffering (vital for container logs)
# - PYTHONDONTWRITEBYTECODE: prevents Python from writing .pyc files to keep disk clean
# - PYTHONPATH: sets root execution path for absolute imports inside the backend folder
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Expose backend service port
EXPOSE 8000

# Native health check to check if application is running and responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c " \
import urllib.request, sys \
try: \
    urllib.request.urlopen('http://localhost:8000/') \
    sys.exit(0) \
except Exception: \
    sys.exit(1) \
"

# Launch startup validation check, and if successful, boot the FastAPI application
# Details:
# - --workers 1: Single worker is recommended for GCP Cloud Run or ECS where scaling is done horizontally via instances rather than multiple processes in a single container.
# - --timeout-keep-alive 75: Configures a high keepalive timeout to robustly support WebSocket connections.
# - --host 0.0.0.0: Binds to all network interfaces to receive external requests.
CMD ["sh", "-c", \
     "python startup_check.py && \
      uvicorn main:app \
      --host 0.0.0.0 \
      --port 8000 \
      --workers 1 \
      --log-level info \
      --timeout-keep-alive 75"]
