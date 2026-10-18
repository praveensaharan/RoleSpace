#!/usr/bin/env bash
# Deploy the public website to Cloud Run as its own service, with a service account that has no roles.
set -euo pipefail
cd "$(dirname "$0")"
PROJECT=${GOOGLE_CLOUD_PROJECT:-project-c399f432-18ea-45d7-b98}
REGION=${REGION:-us-central1}
LB_IP=${LB_IP:-8.232.87.117}   # the load balancer, skipped when the rate limit looks for the caller
gcloud run deploy rolespace-site --source . --region "$REGION" --project "$PROJECT" --quiet \
  --allow-unauthenticated --service-account "rolespace-site@$PROJECT.iam.gserviceaccount.com" \
  --min-instances 0 --max-instances 3 --memory 256Mi --cpu 1 --concurrency 80 --timeout 30 \
  --set-env-vars "^@^TRUSTED_PROXIES=$LB_IP/32,35.191.0.0/16,130.211.0.0/22"
