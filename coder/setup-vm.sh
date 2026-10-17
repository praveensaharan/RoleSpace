#!/usr/bin/env bash
# One-time setup of coder-vm (private subnet, no public IP). Run as root on the VM.
# Installs Docker, Coder (pinned and checksum-verified) and the gateway relay.
set -euo pipefail
CODER_VERSION=2.37.4
GATEWAY_URL=https://rs-gateway-894526891132.us-central1.run.app

apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io python3 >/dev/null
systemctl enable --now docker

cd /tmp
base=https://github.com/coder/coder/releases/download/v$CODER_VERSION
curl -fsSLO $base/coder_${CODER_VERSION}_linux_amd64.deb
curl -fsSLO $base/coder_${CODER_VERSION}_checksums.txt
grep " coder_${CODER_VERSION}_linux_amd64.deb\$" coder_${CODER_VERSION}_checksums.txt | sha256sum -c -
DEBIAN_FRONTEND=noninteractive apt-get install -y -q ./coder_${CODER_VERSION}_linux_amd64.deb >/dev/null

# Coder listens on 3000. People reach it only through an IAP tunnel to localhost:3000,
# so that is also the access URL (workspaces reach it as host.docker.internal).
cat > /etc/coder.d/coder.env <<ENV
CODER_HTTP_ADDRESS=0.0.0.0:3000
CODER_ACCESS_URL=http://localhost:3000
CODER_TELEMETRY_ENABLE=false
CODER_UPDATE_CHECK=false
ENV
usermod -aG docker coder
systemctl enable --now coder

install -m 755 /tmp/gateway-relay.py /usr/local/bin/gateway-relay.py
cat > /etc/systemd/system/gateway-relay.service <<UNIT
[Unit]
Description=Relay from workspaces to the RoleSpace model gateway (adds this VM's Google identity)
After=network-online.target docker.service
[Service]
Environment=GATEWAY_URL=$GATEWAY_URL
Environment=PORT=4000
ExecStart=/usr/bin/python3 /usr/local/bin/gateway-relay.py
Restart=always
DynamicUser=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now gateway-relay
echo "setup done: coder $(coder --version | head -1)"
