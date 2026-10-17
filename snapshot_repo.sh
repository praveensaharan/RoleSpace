#!/usr/bin/env bash
# Copy every project's codebase (role.yaml `projects`) into ./repo/<project id> for the image:
# text files only, each pinned to one commit, so every citation links to exactly the lines the
# agent read.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf repo
mkdir repo
python3 -c 'import yaml; [print(k, v["repo"]) for k, v in yaml.safe_load(open("role.yaml"))["projects"].items()]' |
while read -r id repo; do
  git clone -q --depth 1 "https://github.com/$repo.git" "repo/$id"
  git -C "repo/$id" rev-parse HEAD > "repo/$id/.rolespace-commit"
  rm -rf "repo/$id/.git"
  find "repo/$id" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.pdf' -o -name '*.svg' -o -name '*.woff2' -o -name '*.pptx' \) -delete
  echo "$id: $repo at $(cat "repo/$id/.rolespace-commit")"
done
