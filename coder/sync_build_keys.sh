#!/usr/bin/env bash
# Copy each Build-level person's gateway key (from Secret Manager) to coder-vm, where the
# workspace template reads it. Only Build-level people get a key file, so only they can
# create a workspace. Run after gateway/provision_keys.py.
set -euo pipefail
PROJECT=project-c399f432-18ea-45d7-b98
ROLE_FILE="$(dirname "$0")/../role.yaml"

ids=$(python3 -c 'import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
print(" ".join(p["id"] for p in c["people"] if p["level"] == "build"))' "$ROLE_FILE")

for id in $ids; do
  printf '%s %s\n' "$id" "$(gcloud secrets versions access latest --secret="gw-key-$id" --project=$PROJECT)"
done | gcloud compute ssh coder-vm --zone=us-central1-a --project=$PROJECT --tunnel-through-iap --quiet \
  --command='sudo bash -c "set -e
    d=/var/lib/rolespace/build-keys
    install -d -o coder -g coder -m 700 \$d
    find \$d -type f -delete
    while read -r id key; do
      printf %s \"\$key\" > \$d/\$id; chown coder:coder \$d/\$id; chmod 600 \$d/\$id; echo \"key for \$id\"
    done"' 2>&1 | grep '^key for'
