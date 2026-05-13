# Development Guide

Local setup for the ADA ASM full stack. After following this guide you should be able to reach `http://localhost:8000/api/v1/health` with a 200 response and see the placeholder shell at `http://localhost:5173`.

## Prerequisites

Install:

- **Docker Desktop** (or Colima / Docker Engine) with `docker compose` v2.
- **uv** (`>=0.8`) for backend dependency management — `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **Node.js 20.x** and **pnpm 9.x** (`corepack enable && corepack prepare pnpm@latest --activate`).
- **Git**.

Optional (for pre-commit hooks): **Python 3.12** + `pip install pre-commit`.

## 1. Clone the repository

```bash
git clone git@github-jonsingular:tierraaudio/ada_asm.git
cd ada_asm
```

If you do not use the `github-jonsingular` SSH alias, clone via HTTPS or your own SSH host.

## 2. Configure environment

```bash
cp .env.example .env
```

The defaults are safe for local development. For any non-local environment, generate a real `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. Bring the stack up

```bash
docker compose up --build
```

The first run builds two images (backend + frontend) and pulls Postgres/Redis. Subsequent runs are fast. The orchestration:

1. `postgres` and `redis` come up.
2. `migrate` runs `alembic upgrade head` once (one-shot service).
3. `backend`, `celery_worker`, `celery_beat`, and `frontend` start after migrations finish.

## 4. Verify

| Service        | URL                                                | Expected                                |
| -------------- | -------------------------------------------------- | --------------------------------------- |
| Backend        | http://localhost:8000/api/v1/health                | HTTP 200, `{"status":"ok",...}`         |
| OpenAPI docs   | http://localhost:8000/docs                         | Swagger UI (dev only)                   |
| Frontend       | http://localhost:5173                              | Placeholder shell renders               |
| Frontend health| http://localhost:5173/healthz                      | `ok`                                    |
| Postgres       | `psql postgresql://ada_asm:ada_asm@localhost:5432/ada_asm` | Connects               |
| Redis          | `redis-cli -p 6379 ping`                           | `PONG`                                  |

## 5. View logs

```bash
docker compose logs -f backend
docker compose logs -f celery_worker celery_beat
docker compose logs -f frontend
```

## 6. Day-to-day developer commands

### Backend (`cd backend`)

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000     # local dev server
uv run alembic upgrade head                          # apply migrations
uv run alembic revision --autogenerate -m "<msg>"    # new migration
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run celery -A app.infrastructure.celery_app worker -l info
uv run celery -A app.infrastructure.celery_app beat -l info
```

### Frontend (`cd frontend`)

```bash
pnpm install
pnpm dev                  # Vite dev server (http://localhost:5173)
pnpm typecheck
pnpm lint
pnpm test:run
pnpm test:coverage
pnpm build && pnpm preview
pnpm e2e --grep @smoke    # Playwright smoke set (requires preview server)
```

## 7. Pre-commit hooks

Hooks run on every `git commit`. Install once after cloning:

```bash
pip install pre-commit
pre-commit install
```

Run manually against all files:

```bash
pre-commit run --all-files
```

What the hooks enforce is defined in [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) (lint/format/type checks per stack).

## 8. CI on GitHub

Two workflows live under `.github/workflows/`:

- **`backend.yml`** — runs on PRs touching `backend/**`. Lints, type-checks, runs `pytest` with an 80 % coverage gate.
- **`frontend.yml`** — runs on PRs touching `frontend/**`. Lints, type-checks, runs `vitest` with an 80 % coverage gate, builds, runs the Playwright `@smoke` set.

### Branch protection (operator action)

Set both workflows as **required status checks** for `main` via the GitHub UI:

`Settings → Branches → Add classic rule → Branch name pattern: main → Require status checks to pass → search and select "backend" and "frontend"`.

Without this rule the workflows still run, but failing runs do not block merges.

## 9. Where the rest of the documentation lives

- **Standards**: [`ai-specs/specs/backend-standards.mdc`](backend-standards.mdc) and [`ai-specs/specs/frontend-standards.mdc`](frontend-standards.mdc).
- **Project overview**: [`docs/overview.md`](../../docs/overview.md).
- **Data model catalogue**: [`ai-specs/specs/data-model.md`](data-model.md).
- **API spec**: [`ai-specs/specs/api-spec.yml`](api-spec.yml) — regenerated from `/openapi.json` of the running backend.
- **Change proposals**: `openspec/changes/<name>/`. Archived changes move to `openspec/specs/`.

## 10. Troubleshooting

- **`migrate` exits with `connection refused`** → ensure `postgres` is healthy: `docker compose ps`. Bring just the database up first: `docker compose up -d postgres` and retry.
- **`backend` exits at boot with `pydantic_core._pydantic_core.ValidationError`** → a required env var is missing. The error names the field; add it to `.env` and `docker compose up` again.
- **`pnpm install` fails on host but not container** → corepack version mismatch. `corepack prepare pnpm@latest --activate` then retry.
- **Backend `pytest` fails with `error parsing value for field "cors_origins"`** → `CORS_ORIGINS` must be a comma-separated string, not JSON.
