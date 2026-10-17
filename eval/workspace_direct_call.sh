#!/usr/bin/env bash
# Run try-vertex-directly inside Sam's Coder workspace (via IAP SSH to coder-vm).
P=project-c399f432-18ea-45d7-b98
gcloud secrets versions access latest --secret=coder-password-sam --project $P | \
gcloud compute ssh coder-vm --zone us-central1-a --project $P --tunnel-through-iap --quiet --command '
PW=$(cat); T=$(curl -s -X POST -H "Content-Type: application/json" http://localhost:3000/api/v2/users/login -d "{\"email\":\"sam@firstround.example\",\"password\":\"$PW\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)[\"session_token\"])")
CODER_URL=http://localhost:3000 CODER_SESSION_TOKEN=$T coder ssh firstround "try-vertex-directly"' 2>/dev/null
