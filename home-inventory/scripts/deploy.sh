#!/usr/bin/env bash
# Deploy to Cloud Run. One command, no console steps.
set -euo pipefail

PROJECT=${PROJECT:-my-stuff-inventory}
REGION=${REGION:-europe-north1}
SERVICE=${SERVICE:-my-stuff}
SERVICE_ACCOUNT="inventory-app@${PROJECT}.iam.gserviceaccount.com"

cd "$(dirname "$0")/.."

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --port 8080 \
  `# 1 GiB because a 48MP photo decodes to ~145MB of RGB, and the tmpfs database shares it.` \
  --memory 1Gi \
  --cpu 1 \
  `# Exactly one writer, and nothing running (or billed) when the app is idle.` \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 20 \
  --timeout 120 \
  --set-env-vars "STORAGE_BACKEND=gcs,MEDIA_BUCKET=${PROJECT}-media,DB_BUCKET=${PROJECT}-db,DB_PATH=/srv/data/inventory.sqlite,GCP_PROJECT=${PROJECT},GEMINI_LOCATION=global,GEMINI_MODEL=gemini-3.1-flash-lite,GEMINI_IMAGE_MODEL=gemini-3.1-flash-image" \
  --set-secrets "APP_PASSWORD=inventory-app-password:latest,SESSION_SECRET=inventory-session-key:latest"

echo
echo "Deployed: $(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
