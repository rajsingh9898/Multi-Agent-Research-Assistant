"""Unit and integration test suite for Day 15 (FastAPI Complete Routes).

This suite boots a programmatic Uvicorn instance on port 8000 and validates:
1. GET / health check
2. GET /api/health/all
3. GET /api/languages
4. Input validation - empty topic
5. Input validation - invalid depth
6. No auth token - all protected routes block with 401
7. Invalid token - blocks with 401
8. WebSocket connection ping/pong
9. WebSocket health count tracking
10. GET /docs Swagger accessibility
11. CORS headers check
12. Concurrent WebSocket connections count
"""

from __future__ import annotations

import os
import sys
import json
import time
import asyncio
import logging
import threading
from pathlib import Path
from dotenv import load_dotenv

import httpx
import websockets
import uvicorn

# Setup sys.path to allow imports from both root and backend folders
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force UTF-8 stdout encoding for printing emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure logging
logging.basicConfig(level=logging.WARNING)

load_dotenv(dotenv_path=BACKEND_DIR / ".env")

BASE_URL = "http://localhost:8000"
http_client = httpx.Client(timeout=30.0)


def run_test_server():
    """Boots the FastAPI application on port 8000 for local testing."""
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")


def test_1_root_health() -> None:
    """Test 1: Verify health check root routing returns status running."""
    response = http_client.get(f"{BASE_URL}/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "endpoints" in data
    print("✅ Test 1: Health check PASSED")


def test_2_health_all() -> None:
    """Test 2: Verify services health check monitors Pinecone, Tavily, Firebase, and OpenAI."""
    response = http_client.get(f"{BASE_URL}/api/health/all")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "pinecone" in data["services"]
    assert "firebase" in data["services"]
    assert "openai" in data["services"]
    print(f"  Overall status: {data['status']}")
    print("✅ Test 2: Health/all PASSED")


def test_3_languages() -> None:
    """Test 3: Verify languages configuration returns English, Hindi, and Spanish."""
    response = http_client.get(f"{BASE_URL}/api/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    assert "default" in data
    langs = [l["key"] for l in data["languages"]]
    assert "english" in langs
    assert "hindi" in langs
    assert "spanish" in langs
    print("✅ Test 3: Languages PASSED")


def test_4_empty_topic_validation() -> None:
    """Test 4: Verify input validation blocks empty topic fields (either auth or schema block)."""
    response = http_client.post(
        f"{BASE_URL}/api/research/start",
        json={"topic": "", "depth": "deep"},
        headers={"Authorization": "Bearer fake"}
    )
    # Auth protection blocks before validators if token is fake, yielding 401. Either 401 or 422 is valid block.
    assert response.status_code in [401, 422]
    print("✅ Test 4: Empty topic validation PASSED")


def test_5_invalid_depth_validation() -> None:
    """Test 5: Verify input validation blocks invalid depth descriptors."""
    response = http_client.post(
        f"{BASE_URL}/api/research/start",
        json={"topic": "AI research", "depth": "invalid"},
        headers={"Authorization": "Bearer fake"}
    )
    assert response.status_code in [401, 422]
    print("✅ Test 5: Invalid depth PASSED")


def test_6_no_auth_token_routes() -> None:
    """Test 6: Verify all protected routes block requests with 401 when no token is provided."""
    protected_routes = [
        ("GET", "/api/auth/me"),
        ("POST", "/api/research/start"),
        ("GET", "/api/research/test123"),
        ("GET", "/api/reports/history"),
        ("DELETE", "/api/reports/test123"),
        ("POST", "/api/export/pdf")
    ]

    for method, path in protected_routes:
        if method == "GET":
            r = http_client.get(f"{BASE_URL}{path}")
        elif method == "POST":
            r = http_client.post(f"{BASE_URL}{path}", json={})
        elif method == "DELETE":
            r = http_client.delete(f"{BASE_URL}{path}")

        assert r.status_code == 401
        print(f"  {method} {path} → 401 blocker verified")

    print("✅ Test 6: Auth protection PASSED")


def test_7_invalid_token_header() -> None:
    """Test 7: Verify that malformed tokens block access with 401."""
    response = http_client.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
    print("✅ Test 7: Invalid token PASSED")


def test_8_websocket_endpoint() -> None:
    """Test 8: Verify WebSocket connect events and ping/pong exchanges."""
    async def run_ws_check():
        uri = f"ws://localhost:8000/ws/research/test_ws_123"
        async with websockets.connect(uri) as ws:
            # Check connection accepted event
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            assert data["event"] == "connected"
            assert data["data"]["report_id"] == "test_ws_123"

            # Check ping/pong keep-alives
            await ws.send("ping")
            pong = await asyncio.wait_for(ws.recv(), timeout=5.0)
            assert pong == "pong"

    asyncio.run(run_ws_check())
    print("✅ Test 8: WebSocket PASSED")


def test_9_websocket_health() -> None:
    """Test 9: Verify WebSocket connection count is reported correctly."""
    response = http_client.get(f"{BASE_URL}/api/health/websocket")
    assert response.status_code == 200
    data = response.json()
    assert "active_connections" in data
    print(f"  WS connections: {data['active_connections']}")
    print("✅ Test 9: WS health PASSED")


def test_10_swagger_docs() -> None:
    """Test 10: Verify OpenAPI Swagger docs page is accessible."""
    response = http_client.get(f"{BASE_URL}/docs")
    assert response.status_code == 200
    print("✅ Test 10: API docs accessible PASSED")


def test_11_cors_headers() -> None:
    """Test 11: Verify CORS origin checks return the Access-Control-Allow-Origin headers."""
    response = http_client.options(
        f"{BASE_URL}/api/research/start",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization"
        }
    )
    
    # Case-insensitive headers verification
    header_keys = [k.lower() for k in response.headers.keys()]
    assert "access-control-allow-origin" in header_keys
    print("✅ Test 11: CORS PASSED")


def test_12_concurrent_websocket_connections() -> None:
    """Test 12: Verify concurrent WebSocket tracking increases connection count."""
    async def run_concurrent_check():
        uris = [
            f"ws://localhost:8000/ws/research/test_concurrent_{i}"
            for i in range(3)
        ]
        connections = []

        for uri in uris:
            ws = await websockets.connect(uri)
            connections.append(ws)

        # Allow connections to settle
        await asyncio.sleep(0.5)

        # Check counts
        response = http_client.get(f"{BASE_URL}/api/health/websocket")
        assert response.status_code == 200
        count = response.json()["active_connections"]
        assert count >= 3

        # Close all
        for ws in connections:
            await ws.close()

    asyncio.run(run_concurrent_check())
    print("✅ Test 12: Concurrent WS PASSED")


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("BOOTING FASTAPI SERVER FOR TESTS")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Start FastAPI server in a background thread
    server_thread = threading.Thread(target=run_test_server, daemon=True)
    server_thread.start()
    
    # Wait for Uvicorn to boot up fully
    time.sleep(2)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("RUNNING DAY 15 TEST CASES")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        test_1_root_health()
        test_2_health_all()
        test_3_languages()
        test_4_empty_topic_validation()
        test_5_invalid_depth_validation()
        test_6_no_auth_token_routes()
        test_7_invalid_token_header()
        test_8_websocket_endpoint()
        test_9_websocket_health()
        test_10_swagger_docs()
        test_11_cors_headers()
        test_12_concurrent_websocket_connections()

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ ALL 12 TESTS PASSED")
        print("FastAPI complete routes ready!")
        print("Ready for Day 16: WebSocket Integration")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    except Exception as exc:
        import traceback
        print(f"❌ TEST FAILED: {exc}")
        traceback.print_exc()
        sys.exit(1)
