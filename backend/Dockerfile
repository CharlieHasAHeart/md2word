FROM registry.cloudbility.com.cn/charmirror/python@sha256:cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache

RUN pip install --no-cache-dir uv

FROM base AS dev
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --extra test
WORKDIR /app
CMD ["sh", "-lc", "cd /app/backend && uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"]

FROM base AS prod
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend /app/backend
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app
EXPOSE 8000

CMD ["sh", "-lc", "cd /app/backend && exec /app/backend/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
