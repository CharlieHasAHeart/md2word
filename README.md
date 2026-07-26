# multi-app Workspace

A container-first workspace for hosting multiple tools behind one FastAPI backend and one React frontend.

## Overview

This repository is the shared shell.
It currently ships one app:

- `md2word`: convert Markdown into Word (`.docx`) documents

The backend, frontend, testing approach, and deployment shape are designed so more apps can be added later without creating a separate repo per tool.

## Stack

- FastAPI backend
- Vite + React + TypeScript frontend
- `uv` for Python environment management
- Docker Compose for container-first development

## Quick Start

Preferred:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Then use the running containers for routine work:

```bash
docker exec multi-space-backend-dev sh -lc 'cd /app/backend && uv run pytest -q'
docker exec multi-space-frontend-dev sh -lc 'cd /app/frontend && npm test'
docker exec multi-space-frontend-dev sh -lc 'cd /app/frontend && npm run build'
```

Default local endpoints:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

## Workspace Docs

- [Adding a New App](docs/adding-a-new-app.md)
- [md2word README](docs/README.md)
- [Agent Rules](AGENTS.md)

## License

Apache-2.0
