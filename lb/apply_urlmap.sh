#!/usr/bin/env bash
# Apply lb/urlmap.yaml to the load balancer: website at the root, the app under /rolespace-ent/.
#   ./lb/apply_urlmap.sh            validate, then import
#   ./lb/apply_urlmap.sh --check    validate only
set -euo pipefail
cd "$(dirname "$0")"
PROJECT=${GOOGLE_CLOUD_PROJECT:-project-c399f432-18ea-45d7-b98}
DOMAIN=${DOMAIN:-rolespace.duckdns.org}
BACKENDS="https://www.googleapis.com/compute/v1/projects/$PROJECT/global/backendServices"
map=$(mktemp --suffix=.yaml)
trap 'rm -f "$map"' EXIT
sed -e "s|__BACKENDS__|$BACKENDS|g" -e "s|__DOMAIN__|$DOMAIN|g" urlmap.yaml > "$map"
gcloud compute url-maps validate --global --project "$PROJECT" --source "$map" \
  --load-balancing-scheme=EXTERNAL_MANAGED --format="value(result.loadSucceeded,result.testPassed)"
[ "${1:-}" = "--check" ] && exit 0
gcloud compute url-maps export rolespace-urlmap --global --project "$PROJECT" \
  --destination "urlmap.before-$(date -u +%Y%m%d-%H%M%S).yaml"   # the previous map, to roll back
gcloud compute url-maps import rolespace-urlmap --global --project "$PROJECT" --source "$map" --quiet
