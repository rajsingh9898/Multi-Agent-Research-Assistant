# GCP Cloud Run Deployment Guide
## Multi-Agent Research Assistant Backend

This guide outlines step-by-step setup, CLI initialization, image building, Secret Manager setup, deployment commands, monitoring logs, and exact troubleshooting steps for Day 26.

---

### STEP 1: GCP Account & Project Setup

#### PART A: Create GCP Account
1. Go to: [GCP Free Tier](https://cloud.google.com/free)
2. Click **Get started for free**, sign in, and accept terms.
3. Add billing info (not charged during 90-day free trial containing $300 credits).
4. Free quotas: Cloud Run (2M requests/month), Artifact Registry, and Cloud Build (120 min/day).

#### PART B: Project Creation
- **Via Console**: Go to [Cloud Console](https://console.cloud.google.com), select project selector, click **New Project**, name it `research-assistant`, and copy the auto-generated **Project ID** (e.g. `research-assistant-XXXXXX`).
- **Via CLI**:
  ```bash
  gcloud projects create research-assistant-RAJ
  gcloud config set project research-assistant-RAJ
  ```
- Export Project ID variable:
  ```bash
  export PROJECT_ID="research-assistant-XXXXXX"
  ```

#### PART C: Enable Required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

#### PART D: Set Up Billing Alert
1. Go to: `console.cloud.google.com/billing`
2. Select budget account, click **Budgets & alerts** -> **Create budget**.
3. Name it **Portfolio Protection**, set amount to **$5**, and configure alerting thresholds at **50%**, **90%**, and **100%** to send email notices.

---

### STEP 2: Install and Configure GCloud CLI

- **Windows**: Download and run [GCloud SDK Installer](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe).
- **macOS**: `brew install --cask google-cloud-sdk`
- **Linux**: `sudo snap install google-cloud-cli --classic`

Configure authentication:
```bash
# Login
gcloud auth login

# Select active project
gcloud config set project $PROJECT_ID

# Setup Docker config helper
gcloud auth configure-docker
```

---

### STEP 3: Push Docker Image via Cloud Build

Build on GCP Cloud build servers (faster upload):
```bash
cd backend/
gcloud builds submit --tag gcr.io/$PROJECT_ID/research-backend:latest --timeout=20m .
```

---

### STEP 4: Store Firebase Key in Secret Manager

The private key is multi-line. Storing it as a normal environment variable will cause escaping newline bugs.

1. Go to **Security** -> **Secret Manager** on Cloud Console.
2. Click **Create Secret**, name it `firebase-private-key`, and paste the actual multi-line text (no `\n` abbreviations, paste true newlines).
3. Grant access permissions to the Cloud Run service account:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   gcloud secrets add-iam-policy-binding firebase-private-key \
     --role="roles/secretmanager.secretAccessor" \
     --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
   ```

---

### STEP 5: Deploy to Cloud Run

Use the [deploy.sh](file:///c:/Users/Raj%20Singh/Desktop/multi-agent-research/backend/deploy.sh) script to deploy to Cloud Run:
```bash
chmod +x deploy.sh
./deploy.sh
```

Or run manually:
```bash
gcloud run deploy research-backend \
  --image gcr.io/$PROJECT_ID/research-backend:latest \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300 \
  --execution-environment gen2 \
  --project $PROJECT_ID
```

#### Update Environment Settings
Set normal env vars:
```bash
gcloud run services update research-backend \
  --region asia-south1 \
  --update-env-vars \
"OPENAI_API_KEY=sk-your-openai-key-here,\
TAVILY_API_KEY=tvly-your-tavily-key-here,\
TAVILY_SEARCH_DEPTH=basic,\
TAVILY_MAX_RESULTS=4,\
PINECONE_API_KEY=pcsk-your-pinecone-key-here,\
PINECONE_INDEX_NAME=research-chunks,\
PINECONE_INDEX_HOST=https://research-chunks-xxx.pinecone.io,\
FIREBASE_PROJECT_ID=your-firebase-project-id,\
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com,\
FIREBASE_STORAGE_BUCKET=your-project.appspot.com,\
BACKEND_URL=https://research-backend-xyz.run.app,\
FRONTEND_URL=https://your-frontend.vercel.app"
```

Map Firebase Private Key secret:
```bash
gcloud run services update research-backend \
  --region asia-south1 \
  --update-secrets "FIREBASE_PRIVATE_KEY=firebase-private-key:latest"
```

---

### STEP 6: Troubleshooting Deployed Containers

#### ISSUE 1: "Permission denied" pushing to GCR
- **Fix**: Re-authenticate the Docker daemon:
  ```bash
  gcloud auth configure-docker
  gcloud auth login --update-adc
  ```

#### ISSUE 2: Cloud Run build fails
- **Fix**: Pull logs using:
  ```bash
  gcloud builds list --limit=3
  gcloud builds log BUILD_ID
  ```
  Fix package naming errors in `requirements.txt` or Dockerfile syntax errors locally.

#### ISSUE 3: Container crashes on Cloud Run
- **Fix**: Pull Cloud Run logs:
  ```bash
  gcloud logs read --service=research-backend --region=asia-south1 --limit=50
  ```

#### ISSUE 4: Firebase auth private key invalid
- **Fix**: Mount the secret from Secret Manager correctly as specified in Step 4. Ensure it has literal newlines, not escaped `\n` characters.

#### ISSUE 5: CORS errors in browser
- **Fix**: Update CORS origin target:
  ```bash
  gcloud run services update research-backend --region asia-south1 --update-env-vars "FRONTEND_URL=https://your-exact-vercel-url.vercel.app"
  ```

#### ISSUE 6: WebSocket fails in production
- **Fix**: Verify `--execution-environment gen2` is active, and the frontend connects with `wss://` instead of `ws://`.

#### ISSUE 7: Slow Cold Starts
- **Fix**: (Optional) Keep a container warm (costs slightly more):
  ```bash
  gcloud run services update research-backend --region asia-south1 --min-instances 1
  ```

#### ISSUE 8: Pinecone Dimension Mismatch
- **Fix**: Confirm that `PINECONE_INDEX_NAME` and `PINECONE_INDEX_HOST` environment settings match the correct index dimension (1536 for OpenAI `text-embedding-3-small`).

---

### STEP 7: Monitoring Deployed Instances

#### tail live logs:
```bash
gcloud logs tail "resource.type=cloud_run_revision AND resource.labels.service_name=research-backend"
```

#### Read recent logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=research-backend" --limit=50 --format="table(timestamp,textPayload)"
```

#### Read error logs only:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=research-backend AND severity>=ERROR" --limit=20
```
