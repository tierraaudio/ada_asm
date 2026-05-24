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

## 3b. First-run: seed an administrator

Until a sign-up endpoint exists, the first user is created by a one-shot script. While the stack is up:

```bash
docker compose run --rm backend python -m app.scripts.seed_admin \
  --email founder@yourcompany.com \
  --password 'pick a long, unguessable passphrase'
```

The command refuses with a non-zero exit when any admin already exists. The user can then sign in at `http://localhost:5173`.

### Seed sample components (optional, dev only)

To get a populated `/components` catalogue on a fresh clone — useful for designing against real data and for the Playwright `@smoke` flows:

```bash
docker compose run --rm backend python -m app.scripts.seed_components
```

Inserts ten Figma-flavoured components (ACS712, BME280, ESP32-WROOM-32E, …) plus 3–6 `ComponentPurchase` rows per component so the chart and history views render. The script refuses with exit 2 if the `components` table is non-empty; pass `--reset` to truncate `component_purchases` + `components` first. Random values are deterministically seeded (`random.seed(42)`) so repeated runs produce the same data.

### Seed sample modules (optional, dev only)

After seeding components, populate the `/modules` catalogue with the three reusable assemblies from the Figma (Módulo Sensor Ambiental, Etapa Driver, Sistema Potencia BLDC) — the seed also wires the DAG (Sistema Potencia BLDC contains Etapa Driver as a sub-module + the STM32 MCU is shared with Sensor Ambiental):

```bash
docker compose run --rm backend python -m app.scripts.seed_modules
```

Pass `--reset` to truncate `module_children` + `modules` first. The script exits with 3 if the referenced components aren't already seeded; exits with 2 if `modules` is non-empty without `--reset`.

### Password recovery in development

`SMTP_HOST` is empty by default, so the backend uses the `ConsoleEmailSender`: instead of dispatching a real email, it emits a structured log line tagged `email.console.delivery` with `dev_only=true`. To find the reset link locally, watch the backend logs:

```bash
docker compose logs -f backend | grep email.console.delivery
```

The reset URL is built from `FRONTEND_BASE_URL` (default `http://localhost:5173`).

### Refresh-token storage trade-off

The frontend stores the refresh token in `localStorage` so hard reloads can recover a session. The access token lives in memory only (15-min TTL). This is XSS-attractive; the assumption today is that the app does not render untrusted HTML. Revisit when we deploy publicly: HttpOnly cookies + CSRF protection is the next stop.

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

### Branch protection

Intentionally **not** enabled. The project follows a direct-to-`main` workflow: commits and merges land on `main` without a required PR review or required status checks. CI still runs on every push to `main` (and on any PR that does get opened), and red CI is treated as a strong signal to revert or hotfix — but it does not mechanically block merges. Revisit if the team grows beyond direct trusted contributors.

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
