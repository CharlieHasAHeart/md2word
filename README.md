# md2word Workspace

A multi-app workspace built with FastAPI, Vite, React, and TypeScript.

## Overview

This repository currently ships one tool:

- `md2word`: convert Markdown into Word (`.docx`) documents

The workspace shell is designed to host more tools over time behind a shared backend and frontend.

## Stack

- FastAPI backend
- Vite + React + TypeScript frontend
- `uv` for Python environment management
- Docker Compose for container-first development

## Quick Start

### Preferred: Container-first

Start the development services first:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Then use the running containers for routine work:

```bash
docker exec md2word-backend-dev sh -lc 'cd /app/backend && uv run pytest -q'
docker exec md2word-frontend-dev sh -lc 'cd /app/frontend && npm test'
docker exec md2word-frontend-dev sh -lc 'cd /app/frontend && npm run build'
```

Default local endpoints:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

### Secondary: Host convenience

Use host commands only when container execution is not practical:

```bash
uv sync --project backend
uv run --project backend python -m backend.main

cd frontend
npm install
npm run dev
```

## CLI

```bash
uv run --project backend md2word -i input.md -t backend/md2word/templates/reference.docx -o output.docx
```

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean -i samples/input.md -o samples/cleaned.md --body-output samples/body.md --meta-output samples/meta.json'
```

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean -i samples/input.md --compare-output samples/compare-case-01'
```

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run md2word-clean-regress --compare-output-root /tmp/md2word-regression-run'
```

## Build

Preferred:

```bash
docker exec md2word-frontend-dev sh -lc 'cd /app/frontend && npm run build'
```

Fallback:

```bash
cd frontend
npm run build
```

## Docker

Development:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Production-style local run:

```bash
docker compose up --build
```

Then open:

- `http://127.0.0.1:8080`

## Documentation

- [Adding a New App](docs/adding-a-new-app.md)
- [Markdown Output Spec](docs/markdown-output-spec.md)
- [Agent Rules](AGENTS.md)

## License

Apache-2.0
