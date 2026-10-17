#!/usr/bin/env bash
# Snapshot the demo repo and deploy the RoleSpace app to Cloud Run.
set -euo pipefail
cd "$(dirname "$0")"
PROJECT=project-c399f432-18ea-45d7-b98
./snapshot_repo.sh
gcloud run deploy rolespace --source . --region us-central1 --project $PROJECT --quiet \
  --service-account rolespace-run@$PROJECT.iam.gserviceaccount.com \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT,GATEWAY_URL=https://rs-gateway-894526891132.us-central1.run.app,GITHUB_REPO=praveensaharan/firstround-demo \
  --memory 2Gi --cpu 1 --min-instances 1 --max-instances 1 --timeout 300
