#!/usr/bin/env bash
# Copy the demo codebase into ./repo for the image: text files only, pinned to one commit,
# so every citation links to exactly the lines the agent read.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf repo
git clone -q --depth 1 https://github.com/praveensaharan/firstround-demo.git repo
git -C repo rev-parse HEAD > repo/.rolespace-commit
rm -rf repo/.git
find repo -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.pdf' -o -name '*.svg' \) -delete
echo "repo snapshot at $(cat repo/.rolespace-commit)"
