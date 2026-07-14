#!/bin/bash
# backend/test_gcp_deployment.sh
# Tests the deployed Cloud Run backend
# Usage: ./test_gcp_deployment.sh https://your-url.run.app

set -e

# ── GET URL ──
if [ -z "$1" ]; then
  # Try to get URL from gcloud
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
  if [ -n "$PROJECT_ID" ]; then
    BACKEND_URL=$(gcloud run services describe \
      research-backend \
      --region asia-south1 \
      --format "value(status.url)" \
      2>/dev/null || echo "")
  fi
else
  BACKEND_URL="$1"
fi

if [ -z "$BACKEND_URL" ]; then
  echo "❌ Could not determine backend URL"
  echo "Usage: ./test_gcp_deployment.sh https://your-url.run.app"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     GCP DEPLOYMENT TEST                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Testing: $BACKEND_URL"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# Ensure a temporary file is cleaned up on exit
trap 'rm -f /tmp/test_response.txt' EXIT

run_test() {
  local NAME="$1"
  local EXPECTED_CODE="$2"
  local URL="$3"
  local CHECK_CONTENT="$4"
  
  echo -n "  Testing $NAME... "
  
  HTTP_CODE=$(curl -s -o /tmp/test_response.txt \
    -w "%{http_code}" \
    --max-time 30 \
    "$URL" 2>/dev/null || echo "000")
  
  RESPONSE=$(cat /tmp/test_response.txt 2>/dev/null || echo "")
  
  CODE_OK=false
  if [ "$HTTP_CODE" = "$EXPECTED_CODE" ]; then
    CODE_OK=true
  fi
  
  CONTENT_OK=true
  if [ -n "$CHECK_CONTENT" ]; then
    if ! echo "$RESPONSE" | grep -q "$CHECK_CONTENT"; then
      CONTENT_OK=false
    fi
  fi
  
  if $CODE_OK && $CONTENT_OK; then
    echo "✅ $HTTP_CODE OK"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    if ! $CODE_OK; then
      echo "❌ Got $HTTP_CODE, expected $EXPECTED_CODE"
    else
      echo "❌ Missing '$CHECK_CONTENT' in response"
      echo "     Response: $(echo "$RESPONSE" | head -c 100)"
    fi
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

# ── HEALTH TESTS ──
echo "🏥 Health Endpoint Tests:"
run_test "GET /" "200" "$BACKEND_URL/" "running"
run_test "GET /api/health/all" "200" "$BACKEND_URL/api/health/all" "services"
run_test "GET /api/health/websocket" "200" "$BACKEND_URL/api/health/websocket" "active_connections"
run_test "GET /api/health/pdf" "200" "$BACKEND_URL/api/health/pdf" "status"
run_test "GET /api/health/pinecone" "200" "$BACKEND_URL/api/health/pinecone" "status"

# ── PUBLIC TESTS ──
echo ""
echo "🌐 Public Endpoint Tests:"
run_test "GET /api/languages" "200" "$BACKEND_URL/api/languages" "english"
run_test "GET /docs" "200" "$BACKEND_URL/docs" ""
run_test "GET /redoc" "200" "$BACKEND_URL/redoc" ""

# ── AUTH PROTECTION TESTS ──
echo ""
echo "🔒 Auth Protection Tests:"
run_test "GET /api/auth/me (no token)" "401" "$BACKEND_URL/api/auth/me" ""
run_test "GET /api/reports/history (no token)" "401" "$BACKEND_URL/api/reports/history" ""
run_test "POST /api/research/start (no token)" "401" "$BACKEND_URL/api/research/start" ""

# ── CORS TEST ──
echo ""
echo "🌍 CORS Test:"
echo -n "  Testing CORS headers... "
CORS_HEADERS=$(curl -s -I \
  -H "Origin: https://your-frontend.vercel.app" \
  "$BACKEND_URL/" 2>/dev/null || echo "")

if echo "$CORS_HEADERS" | grep -qi "access-control"; then
  echo "✅ CORS headers present"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "⚠️  CORS headers not detected (may be OK)"
fi

# ── RESPONSE TIME TEST ──
echo ""
echo "⚡ Performance Test:"
echo -n "  Testing response time... "
RESPONSE_TIME=$(curl -s -o /dev/null \
  -w "%{time_total}" \
  --max-time 10 \
  "$BACKEND_URL/" 2>/dev/null || echo "999")

echo "${RESPONSE_TIME}s"
# Use awk or standard bash comparison to check total time
IS_FAST=$(echo "$RESPONSE_TIME < 3.0" | bc -l 2>/dev/null || echo "0")
if [ "$IS_FAST" = "1" ] || [ "$RESPONSE_TIME" = "0" ]; then
  echo "  ✅ Response time under 3 seconds"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "  ⚠️  Slow response (cold start?) - try again"
fi

# ── WEBSOCKET TEST ──
echo ""
echo "🔌 WebSocket Test:"
if command -v wscat &> /dev/null; then
  WS_URL="${BACKEND_URL/https/wss}/ws/research/gcp-test"
  echo -n "  Testing WebSocket: $WS_URL ... "
  WS_RESULT=$(echo "" | timeout 5 wscat \
    -c "$WS_URL" \
    2>&1 || true)
  
  if echo "$WS_RESULT" | grep -qi "connected\|event\|research"; then
    echo "✅ WebSocket connected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "⚠️  Could not verify WebSocket"
    echo "    Try manually: wscat -c $WS_URL"
  fi
else
  echo "  ⚠️  wscat not installed"
  echo "  Install: npm install -g wscat"
  echo "  Then: wscat -c ${BACKEND_URL/https/wss}/ws/research/test"
fi

# ── SUMMARY ──
echo ""
echo "╔══════════════════════════════════════════╗"
TOTAL=$((TESTS_PASSED + TESTS_FAILED))
if [ $TESTS_FAILED -eq 0 ]; then
  echo "║  ✅ ALL TESTS PASSED: $TESTS_PASSED/$TOTAL"
else
  echo "║  ⚠️  SOME ISSUES: $TESTS_PASSED/$TOTAL passed"
fi
echo "║"
echo "║  Backend URL:"
echo "║  $BACKEND_URL"
echo "╚══════════════════════════════════════════╝"

echo ""
echo "📋 NEXT STEPS:"
echo "  1. Update frontend .env.local:"
echo "     NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL"
echo ""
echo "  2. Test complete flow:"
echo "     Start frontend: cd frontend && npm run dev"
echo "     Open: http://localhost:3000"
echo "     Try: Start a research run"
echo ""
echo "  3. Deploy frontend (Day 27):"
echo "     Deploy to Vercel"
echo "     Update FRONTEND_URL in Cloud Run"
