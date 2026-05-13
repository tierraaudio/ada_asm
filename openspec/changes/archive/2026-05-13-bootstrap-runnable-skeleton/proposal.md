## Why

The repository currently contains standards, Docker scaffolding and a `docker-compose.yml`, but **no runnable code**. `docker compose up` cannot bring the stack up because there is no `pyproject.toml`, no `package.json`, no Alembic baseline, no FastAPI app and no React entry point. CI is documented in the standards but has no workflow files. Before the first user story (Login en ASM 1.0) can be implemented and validated end-to-end, the project needs a green skeleton: an app that boots, a CI that passes on an empty change, and the developer onboarding docs that go with them.

## What Changes

- **Backend boot skeleton**: minimal FastAPI app (`backend/app/main.py`) with a `GET /api/v1/health` endpoint, Pydantic Settings (`app/core/config.py`), structlog setup, and the layered folder structure pre-created (empty `__init__.py` files) as documented in `ai-specs/specs/backend-standards.mdc`.
- **Backend package management**: `pyproject.toml` (uv-managed) pinning Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, psycopg, asyncpg, structlog, python-jose, passlib[argon2]; dev deps pytest, pytest-asyncio, httpx, ruff, mypy, pytest-cov. `uv.lock` committed.
- **Alembic baseline migration**: `backend/alembic.ini` + `backend/migrations/env.py` + one empty initial revision that enables required Postgres extensions (`pgcrypto`, `ltree`). No business tables in this change.
- **Celery skeleton**: `app/infrastructure/celery_app.py` (factory only) so the `celery_worker` and `celery_beat` containers boot without errors. No tasks defined yet.
- **Frontend boot skeleton**: `package.json` (pnpm), `vite.config.ts`, `tsconfig.json`, `tailwind.config.ts`, ESLint + Prettier config, Vitest config, Playwright config (no tests yet). `src/main.tsx`, `src/App.tsx`, `src/app/layout/DashboardLayout.tsx` rendering a placeholder shell.
- **`.env.example`**: documents every variable referenced by `docker-compose.yml` and the two standards files (`DATABASE_URL`, `POSTGRES_*`, `REDIS_*`, `CELERY_BROKER_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `VITE_API_URL`, port overrides).
- **GitHub Actions workflows**: `.github/workflows/backend.yml` (uv sync → ruff → mypy → pytest with 80% gate) and `.github/workflows/frontend.yml` (pnpm install → eslint → typecheck → vitest → build → playwright smoke). Triggered on PRs touching the respective directories and on pushes to `main`.
- **Initial documentation**: skeleton (with headings + the structure documented in the standards) for `ai-specs/specs/data-model.md` (lists the entities planned per `docs/overview.md` but leaves table definitions for follow-up USs) and `ai-specs/specs/development_guide.md` (clone → env → `docker compose up` → access URLs → next steps).

**Non-goals (explicit)**:
- No business endpoints (projects, modules, components, auth) — those belong to the User Stories.
- No SQLAlchemy models for business entities, no Pydantic schemas for them, no Celery tasks for them.
- No production deploy workflow — only PR validation CI.

## Capabilities

### New Capabilities
- `runnable-skeleton`: A bootable, end-to-end skeleton — `docker compose up` brings backend, frontend, postgres, redis, celery worker and beat to a healthy state; backend exposes `/api/v1/health`; frontend serves the placeholder shell; Alembic baseline migration applies cleanly. Includes the `.env.example` contract and developer onboarding doc.
- `continuous-integration`: Automated PR validation for the backend and frontend stacks. Backend pipeline runs lint, type check and tests with an 80% coverage gate. Frontend pipeline runs lint, type check, unit tests, production build and a Playwright smoke test. Both pipelines must be green before a PR can merge.

### Modified Capabilities
_(None — this is the first change; no specs exist yet.)_

## Impact

- **Code**: introduces `backend/app/`, `backend/migrations/`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/alembic.ini`, `frontend/src/`, `frontend/package.json`, `frontend/pnpm-lock.yaml`, top-level `.env.example`, `.github/workflows/backend.yml`, `.github/workflows/frontend.yml`.
- **Docs**: fills in `ai-specs/specs/data-model.md` and `ai-specs/specs/development_guide.md`.
- **Dependencies**: adds runtime deps (FastAPI, SQLAlchemy 2, Alembic, Celery, etc.) and dev deps (ruff, mypy, pytest, vitest, playwright, etc.) — all pinned in lockfiles.
- **External systems**: none in this change. Holded, KiCAT and supplier integrations are out of scope.
- **CI cost**: adds ~2 GitHub Actions runs per PR (one per workflow); both cached aggressively.
- **Local dev**: developer can now run `cp .env.example .env && docker compose up` and reach `http://localhost:8000/api/v1/health` (200) and `http://localhost:5173` (placeholder UI).
