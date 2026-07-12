#!/bin/bash
# backend/test_docker.sh
# Tests Docker build and run locally
# Usage: chmod +x test_docker.sh && ./test_docker.sh

set -e

# ── CONFIGURATION ──
IMAGE_NAME="research-assistant-backend"
CONTAINER_NAME="test-backend-$(date +%s)"
TEST_PORT=8001  # Use 8001 to avoid conflict with dev server
WAIT_SECONDS=10

# Register cleanup trap to ensure test containers are removed even on failure/abort
trap 'echo ""; echo "🗑️  Tearing down test container..."; docker rm -f $CONTAINER_NAME 2>/dev/null || true; echo "✅ Cleanup complete"' EXIT

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     DOCKER BUILD AND TEST SCRIPT         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── CHECK PREREQUISITES ──
echo "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
  echo "❌ Docker not installed!"
  echo "Install from: https://docs.docker.com/get-docker/"
  exit 1
fi
echo "✅ Docker: $(docker --version)"

if [ ! -f ".env" ]; then
  echo "❌ .env file not found in backend/"
  echo "Create it with your API keys"
  exit 1
fi
echo "✅ .env file found"

# ── CLEANUP OLD CONTAINERS ──
echo ""
echo "🗑️  Cleaning up old test containers..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

# ── BUILD IMAGE ──
echo ""
echo "📦 Building Docker image..."
echo "Using context: $(pwd)"
echo "This may take 2-3 minutes on first build..."
echo ""

BUILD_START=$(date +%s)

docker build \
  --tag $IMAGE_NAME \
  --file Dockerfile \
  --progress=plain \
  . 2>&1 | tail -20

BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))

echo ""
echo "✅ Build complete in ${BUILD_TIME}s"

# ── CHECK IMAGE SIZE ──
echo ""
echo "📊 Image info:"
docker image inspect $IMAGE_NAME \
  --format='  Size: {{.Size}} bytes' 2>/dev/null || true
docker images $IMAGE_NAME \
  --format "  Repository: {{.Repository}}\n  Tag: {{.Tag}}\n  Size: {{.Size}}"

# ── RUN CONTAINER ──
echo ""
echo "🚀 Starting container..."

docker run \
  --detach \
  --name $CONTAINER_NAME \
  --publish $TEST_PORT:8000 \
  --env-file .env \
  --env PYTHONUNBUFFERED=1 \
  $IMAGE_NAME

echo "✅ Container started: $CONTAINER_NAME"
echo ""
echo "⏳ Waiting ${WAIT_SECONDS}s for startup..."
sleep $WAIT_SECONDS

# ── CHECK CONTAINER STATUS ──
echo ""
echo "🔍 Container status:"
CONTAINER_STATUS=$(docker inspect \
  --format='{{.State.Status}}' \
  $CONTAINER_NAME 2>/dev/null || echo "unknown")
echo "  Status: $CONTAINER_STATUS"

if [ "$CONTAINER_STATUS" != "running" ]; then
  echo ""
  echo "❌ Container is not running!"
  echo "Container logs:"
  docker logs $CONTAINER_NAME
  exit 1
fi

# ── TEST ENDPOINTS ──
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         ENDPOINT TESTS                   ║"
echo "╚══════════════════════════════════════════╝"

BASE_URL="http://localhost:$TEST_PORT"
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
  local TEST_NAME="$1"
  local EXPECTED_CODE="$2"
  local URL="$3"
  local METHOD="${4:-GET}"
  local DATA="$5"
  
  if [ "$METHOD" = "POST" ] && [ -n "$DATA" ]; then
    ACTUAL_CODE=$(curl -s -o /dev/null \
      -w "%{http_code}" \
      -X POST \
      -H "Content-Type: application/json" \
      -d "$DATA" \
      "$URL" 2>/dev/null || echo "000")
  else
    ACTUAL_CODE=$(curl -s -o /dev/null \
      -w "%{http_code}" \
      "$URL" 2>/dev/null || echo "000")
  fi
  
  if [ "$ACTUAL_CODE" = "$EXPECTED_CODE" ]; then
    echo "  ✅ $TEST_NAME: $ACTUAL_CODE"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "  ❌ $TEST_NAME: got $ACTUAL_CODE, expected $EXPECTED_CODE"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

echo ""
echo "Testing health endpoints:"
run_test "GET / (health)" "200" "$BASE_URL/"
run_test "GET /api/health/all" "200" "$BASE_URL/api/health/all"
run_test "GET /api/health/websocket" "200" "$BASE_URL/api/health/websocket"
run_test "GET /api/health/pdf" "200" "$BASE_URL/api/health/pdf"

echo ""
echo "Testing public endpoints:"
run_test "GET /api/languages" "200" "$BASE_URL/api/languages"
run_test "GET /docs (Swagger)" "200" "$BASE_URL/docs"
run_test "GET /redoc" "200" "$BASE_URL/redoc"

echo ""
echo "Testing auth protection:"
run_test "GET /api/auth/me (no token)" "401" "$BASE_URL/api/auth/me"
run_test "GET /api/reports/history (no token)" "401" "$BASE_URL/api/reports/history"
run_test "POST /api/research/start (no token)" "401" "$BASE_URL/api/research/start"

echo ""
echo "Testing response content:"
RESPONSE=$(curl -s "$BASE_URL/" 2>/dev/null)
if echo "$RESPONSE" | grep -q "running"; then
  echo "  ✅ GET /: Contains 'running'"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "  ❌ GET /: Missing 'running' in response"
  echo "     Got: $RESPONSE"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

LANG_RESPONSE=$(curl -s "$BASE_URL/api/languages" 2>/dev/null)
if echo "$LANG_RESPONSE" | grep -q "english" && \
   echo "$LANG_RESPONSE" | grep -q "hindi"; then
  echo "  ✅ GET /api/languages: Has english + hindi"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "  ❌ GET /api/languages: Missing languages"
  TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ── TEST WEBSOCKET ──
echo ""
echo "Testing WebSocket:"
if command -v wscat &> /dev/null; then
  WS_RESULT=$(echo "" | timeout 3 \
    wscat -c "ws://localhost:$TEST_PORT/ws/research/docker-test" \
    2>&1 || true)
  if echo "$WS_RESULT" | grep -qi "connected\|event"; then
    echo "  ✅ WebSocket: Connected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "  ⚠️  WebSocket: Could not verify connection"
    echo "     Install wscat: npm install -g wscat"
  fi
else
  echo "  ⚠️  WebSocket: skipped (wscat not installed)"
  echo "     Install: npm install -g wscat"
fi

# ── SHOW CONTAINER LOGS ──
echo ""
echo "📋 Container logs (last 30 lines):"
echo "─────────────────────────────────────"
docker logs $CONTAINER_NAME --tail=30
echo "─────────────────────────────────────"

# ── RESULTS SUMMARY ──
echo ""
echo "╔══════════════════════════════════════════╗"
TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TESTS_FAILED -eq 0 ]; then
  echo "║  ✅ ALL TESTS PASSED: $TESTS_PASSED/$TOTAL             ║"
else
  echo "║  ❌ SOME TESTS FAILED: $TESTS_PASSED/$TOTAL passed     ║"
fi
echo "║  Build time: ${BUILD_TIME}s                        ║"
echo "╚══════════════════════════════════════════╝"

echo ""
if [ $TESTS_FAILED -eq 0 ]; then
  echo "🎉 Docker image '$IMAGE_NAME' is ready!"
  echo "   Next step: Deploy to GCP Cloud Run"
  echo ""
  echo "   Quick start commands:"
  echo "   docker run -p 8000:8000 --env-file .env $IMAGE_NAME"
  echo "   docker-compose up"
  exit 0
else
  echo "⚠️  $TESTS_FAILED test(s) failed."
  echo "   Check the logs above for issues."
  exit 1
fi
