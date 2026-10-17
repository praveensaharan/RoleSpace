# Workspace image for the RoleSpace team template: Coder's base image plus Node and Gemini CLI.
FROM codercom/example-base:ubuntu
USER root
RUN apt-get update -q && apt-get install -y -q ripgrep && rm -rf /var/lib/apt/lists/*
ARG NODE_VERSION=v24.22.0
ARG GEMINI_CLI_VERSION=0.64.0
RUN cd /tmp \
 && curl -fsSLO https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz \
 && curl -fsSL https://nodejs.org/dist/${NODE_VERSION}/SHASUMS256.txt | grep " node-${NODE_VERSION}-linux-x64.tar.xz\$" | sha256sum -c - \
 && tar -xJf node-${NODE_VERSION}-linux-x64.tar.xz -C /usr/local --strip-components=1 \
 && rm node-*.tar.xz \
 && npm install -g --no-fund --no-audit @google/gemini-cli@${GEMINI_CLI_VERSION}
COPY try-vertex-directly /usr/local/bin/try-vertex-directly
USER coder
