#!/usr/bin/env bash
# Open Coder through Identity-Aware Proxy: coder-vm:3000 -> localhost:3000 on this machine.
# In VS Code (Remote SSH), the Ports tab forwards localhost:3000 on to your own browser.
exec gcloud compute start-iap-tunnel coder-vm 3000 --local-host-port=localhost:3000 \
  --zone=us-central1-a --project=project-c399f432-18ea-45d7-b98
