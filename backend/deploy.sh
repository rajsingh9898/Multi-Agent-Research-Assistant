#!/bin/bash
# backend/deploy.sh
# Full deployment script: build → push → deploy
# Usage: ./deploy.sh [--no-build] [--project PROJECT_ID]

set -e

# ── PARSE ARGUMENTS ──
SKIP_BUILD=false
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="asia-south1"
SERVICE_NAME="research-backend"

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --no-build) SKIP_BUILD=true ;;
    --project) PROJECT_ID="$2"; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

# ── VALIDATE ──
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "❌ PROJECT_ID not set!"
  echo "Usage: GCP_PROJECT_ID=your-id ./deploy.sh"
  echo "OR:    gcloud config set project your-id"
  exit 1
fi

IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       GCP DEPLOYMENT SCRIPT              ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Project:  $PROJECT_ID"
echo "Service:  $SERVICE_NAME"
echo "Region:   $REGION"
echo "Image:    $IMAGE:latest"
echo ""

# ── STEP 1: BUILD ──
if [ "$SKIP_BUILD" = false ]; then
  echo "📦 Building + pushing via Cloud Build..."
  echo "(This builds on GCP - faster than local)"
  
  # Ensure we are in the directory of the script (backend/)
  cd "$(dirname "$0")"
  
  gcloud builds submit \
    --tag $IMAGE:latest \
    --timeout=20m \
    --project=$PROJECT_ID \
    .
  
  echo "✅ Build and push complete"
else
  echo "⏭️  Skipping build (--no-build flag)"
fi

# ── STEP 2: DEPLOY ──
echo ""
echo "🚀 Deploying to Cloud Run..."

gcloud run deploy $SERVICE_NAME \
  --image $IMAGE:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300 \
  --execution-environment gen2 \
  --concurrency 80 \
  --project $PROJECT_ID

# ── STEP 3: GET URL ──
echo ""
SERVICE_URL=$(gcloud run services describe \
  $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format "value(status.url)")

echo "✅ Deployment complete!"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  LIVE URL:"
echo "║  $SERVICE_URL"
echo "╚══════════════════════════════════════════╝"

# ── STEP 4: QUICK TEST ──
echo ""
echo "🧪 Quick health check..."
sleep 5

HTTP_CODE=$(curl -s -o /dev/null \
  -w "%{http_code}" \
  --max-time 30 \
  "$SERVICE_URL/" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Backend is responding!"
else
  echo "⚠️  Backend returned: $HTTP_CODE"
  echo "   May need a moment to start up"
  echo "   Try: curl $SERVICE_URL/"
fi

echo ""
echo "📋 Next steps:"
echo "  1. Set env vars: See STEP 5 in guide"
echo "  2. Run full tests: ./test_gcp_deployment.sh $SERVICE_URL"
echo "  3. Update frontend: NEXT_PUBLIC_BACKEND_URL=$SERVICE_URL"
