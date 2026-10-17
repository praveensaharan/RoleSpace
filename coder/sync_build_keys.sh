#!/usr/bin/env bash
# Hand each Build-level person their gateway key (from Secret Manager) and their repository list
# (RoleSpace > Repo access) on coder-vm, where the workspace template reads both. Only Build-level
# people get a key file, so only they can create a workspace; each workspace clones only that
# person's repositories. People come from the live app, so onboarded members and repo access
# changes are included. Run after gateway/provision_keys.py, onboarding or a repo access change.
set -euo pipefail
PROJECT=project-c399f432-18ea-45d7-b98
URL=$(gcloud run services describe rolespace --region=us-central1 --project=$PROJECT --format='value(status.url)')
people=$(curl -sf -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$URL/api/people")

lines=$(python3 -c 'import json, sys
d = json.load(sys.stdin)
for p in d["people"]:
    if p["base_level"] == "build":
        print(p["id"], " ".join(f"https://github.com/{d['"'"'projects'"'"'][k]['"'"'repo'"'"']}.git" for k in p["projects"]))' <<<"$people")

while read -r id repos; do
  [ -n "$id" ] || continue
  printf 'key %s %s\nrepos %s %s\n' "$id" "$(gcloud secrets versions access latest --secret="gw-key-$id" --project=$PROJECT)" "$id" "$repos"
done <<<"$lines" | gcloud compute ssh coder-vm --zone=us-central1-a --project=$PROJECT --tunnel-through-iap --quiet \
  --command='sudo bash -c "set -e
    k=/var/lib/rolespace/build-keys r=/var/lib/rolespace/build-repos
    install -d -o coder -g coder -m 700 \$k \$r
    find \$k \$r -type f -delete
    while read -r kind id rest; do
      if [ \$kind = key ]; then f=\$k/\$id; printf %s \"\$rest\" > \$f; else f=\$r/\$id; printf \"%s\n\" \$rest > \$f; fi
      chown coder:coder \$f; chmod 600 \$f; echo \"\$kind for \$id\"
    done"' 2>&1 | grep -E '^(key|repos) for'
