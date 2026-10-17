# Model gateway: LiteLLM proxy with Postgres (Cloud SQL) for keys, budgets and spend.
# Pinned to v1.105.1 by digest so a re-tag upstream can't change what we run.
FROM ghcr.io/berriai/litellm-database:v1.105.1@sha256:2bcadb9905b692a5ca4dadd51bccaaa23a95dc8a0f9322d9c9787f0ac2aeb50e

COPY config.yaml /app/config.yaml

# Cloud Run sends traffic to 8080. The image's entrypoint runs `litellm "$@"`.
CMD ["--config", "/app/config.yaml", "--port", "8080", "--num_workers", "1"]
