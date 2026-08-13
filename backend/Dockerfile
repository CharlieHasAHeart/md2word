FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache

RUN pip install --no-cache-dir uv

WORKDIR /app/backend
COPY backend/pyproject.toml /app/backend/pyproject.toml

FROM base AS dev
RUN uv sync --extra test
WORKDIR /app
CMD ["sh", "-lc", "cd /app/backend && uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"]

FROM base AS prod
COPY backend /app/backend
RUN uv sync --no-dev
WORKDIR /app
CMD ["sh", "-lc", "cd /app/backend && uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
