FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY rxconfig.py ./

RUN uv venv /app/.venv && \
    uv pip install --python=/app/.venv/bin/python -e . --no-cache

COPY src/ ./src/

COPY assets/ ./assets/

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

RUN reflex init

# 3000: Reflex frontend (UI)
# 8000: Reflex backend (WebSocket for state sync)
# 8001: FastAPI backend (API)
EXPOSE 3000 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENV MODE=prod

ENTRYPOINT ["/entrypoint.sh"]
