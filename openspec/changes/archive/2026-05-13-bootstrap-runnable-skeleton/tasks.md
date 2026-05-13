## 1. Backend tooling and project layout

- [x] 1.1 Create `backend/pyproject.toml` with Python `>=3.12,<3.13`, project metadata, runtime deps (fastapi, pydantic, pydantic-settings, sqlalchemy[asyncio], alembic, psycopg[binary], asyncpg, celery, redis, structlog, python-jose[cryptography], passlib[argon2], httpx) and dev deps (pytest, pytest-asyncio, pytest-cov, ruff, mypy, types-redis, types-passlib)
- [x] 1.2 Configure tool sections in `pyproject.toml`: `[tool.ruff]` (line-length 100, target-version py312, select sensible rules), `[tool.mypy]` strict mode, `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `[tool.coverage.report]` with `fail_under = 80`
- [x] 1.3 Generate `backend/uv.lock` with `uv lock` and commit it
- [x] 1.4 Create empty `__init__.py` files for the layered structure documented in `backend-standards.mdc`: `app/`, `app/api/`, `app/api/v1/`, `app/api/v1/routers/`, `app/api/v1/schemas/`, `app/application/`, `app/application/services/`, `app/domain/`, `app/domain/entities/`, `app/domain/repositories/`, `app/infrastructure/`, `app/infrastructure/db/`, `app/infrastructure/db/models/`, `app/infrastructure/repositories/`, `app/infrastructure/integrations/`, `app/infrastructure/tasks/`, `app/core/`
- [x] 1.5 Create `backend/app/core/config.py`: `Settings` class with `pydantic_settings.BaseSettings`, fields for `database_url`, `celery_broker_url`, `celery_result_backend`, `jwt_secret`, `cors_origins` (list, parsed from comma-separated env), `env`, `log_level`, `app_version`. Refuse to instantiate if any required field is missing
- [x] 1.6 Create `backend/app/infrastructure/logging.py`: structlog configuration that outputs JSON in non-dev envs and console renderer in dev; bind `request_id` to context vars
- [x] 1.7 Create `backend/app/main.py`: `create_app()` factory returning a `FastAPI` instance; mount a single router with `GET /api/v1/health` returning `{"status": "ok", "version": settings.app_version, "timestamp": <ISO 8601 UTC>}`; install CORS middleware reading from `settings.cors_origins`; install a request-id middleware that sets `X-Request-ID`

## 2. Database baseline migration

- [x] 2.1 Create `backend/alembic.ini` pointing to `backend/migrations/` with the sync `postgresql+psycopg://` URL read from env at runtime
- [x] 2.2 Create `backend/migrations/env.py` configured to read `DATABASE_URL` from env; `target_metadata = None` (no models yet)
- [x] 2.3 Create `backend/migrations/script.py.mako` and the `versions/` directory
- [x] 2.4 Generate the initial revision `<timestamp>_baseline_enable_extensions.py` whose `upgrade()` runs `CREATE EXTENSION IF NOT EXISTS pgcrypto;` and `CREATE EXTENSION IF NOT EXISTS ltree;` and whose `downgrade()` drops them in reverse order
- [x] 2.5 Verify locally: `docker compose up -d postgres && cd backend && uv run alembic upgrade head` then `uv run alembic downgrade base` — both exit 0

## 3. Celery skeleton

- [x] 3.1 Create `backend/app/infrastructure/celery_app.py`: `celery_app = Celery("ada_asm")` with broker/backend from `settings`; `celery_app.conf.task_default_queue = "default"`; no tasks registered; empty `beat_schedule = {}`
- [x] 3.2 Verify locally: `docker compose up -d redis` then `uv run celery -A app.infrastructure.celery_app worker -l info` reports "ready"; same for `beat`

## 4. Backend tests scaffolding

- [x] 4.1 Create `backend/tests/__init__.py`, `backend/tests/conftest.py` with an `api_client` async fixture using `httpx.AsyncClient` against the FastAPI app
- [x] 4.2 Create `backend/tests/unit/test_health.py` covering: 200 + body shape, no auth required, missing env raises at boot (use `monkeypatch.delenv` + `pytest.raises`)
- [x] 4.3 Run `uv run pytest --cov=app` locally; ensure ≥80% coverage on the skeleton (it should be trivially high)

## 5. Frontend tooling and project layout

- [x] 5.1 Create `frontend/package.json` with: name, type=module, scripts (`dev`, `build`, `preview`, `lint`, `format`, `typecheck`, `test`, `test:run`, `test:coverage`, `e2e`, `gen:api`), runtime deps (react, react-dom, react-router-dom, @tanstack/react-query, zustand, axios, react-hook-form, zod, @hookform/resolvers, clsx, tailwind-merge, class-variance-authority, lucide-react), dev deps (vite, @vitejs/plugin-react, typescript, @types/react, @types/react-dom, tailwindcss, postcss, autoprefixer, eslint + plugins, prettier + tailwind plugin, vitest, @vitest/coverage-v8, @testing-library/react, @testing-library/jest-dom, @testing-library/user-event, msw, @playwright/test, @axe-core/playwright, openapi-typescript)
- [x] 5.2 Generate `frontend/pnpm-lock.yaml` with `pnpm install` and commit it
- [x] 5.3 Create `frontend/tsconfig.json` per `frontend-standards.mdc` (strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes, baseUrl, `@/*` path alias)
- [x] 5.4 Create `frontend/vite.config.ts`: react plugin, path alias `@` → `src`, port 5173, dev proxy not needed in this change
- [x] 5.5 Create `frontend/tailwind.config.ts`, `postcss.config.js`, `frontend/src/styles/globals.css` with Tailwind layers and the shadcn CSS variables (`--background`, `--foreground`, etc.) for both light and dark
- [x] 5.6 Create ESLint config (`frontend/.eslintrc.cjs`): `@typescript-eslint`, `eslint-plugin-react`, `react-hooks`, `tailwindcss`, `jsx-a11y`, `prettier` last
- [x] 5.7 Create `frontend/.prettierrc` and `.prettierignore`
- [x] 5.8 Create `frontend/vitest.config.ts` with v8 coverage and 80% thresholds; `frontend/src/tests/setup.ts` with `@testing-library/jest-dom` and MSW server scaffold (no handlers yet)
- [x] 5.9 Create `frontend/playwright.config.ts` with `webServer` pointing at the built preview server; one chromium project; `grep @smoke` semantics for the smoke set

## 6. Frontend skeleton code

- [x] 6.1 Create `frontend/index.html` with the React mount point
- [x] 6.2 Create `frontend/src/main.tsx` mounting `<App />` wrapped in providers (QueryClient, BrowserRouter)
- [x] 6.3 Create `frontend/src/App.tsx` with a single route `/` rendering `<DashboardLayout><div>ADA ASM placeholder</div></DashboardLayout>`
- [x] 6.4 Create `frontend/src/app/layout/DashboardLayout.tsx`, `Header.tsx`, `Sidebar.tsx` — minimal Tailwind markup matching the Figma chassis (256px sidebar + header + content)
- [x] 6.5 Add `frontend/src/lib/utils/cn.ts` (clsx + tailwind-merge helper) and `frontend/src/components/ui/button.tsx` (shadcn primitive) pre-scaffolded manually
- [x] 6.6 Create `frontend/src/lib/api/client.ts`: axios instance reading `import.meta.env.VITE_API_URL`; no interceptors yet (auth lands with US Login)
- [x] 6.7 Create `frontend/e2e/smoke.spec.ts` tagged `@smoke` asserting the placeholder shell renders against the built artifact (`Sidebar`, `Header`, `"ADA ASM placeholder"`)
- [x] 6.8 Run locally: `pnpm install && pnpm lint && pnpm typecheck && pnpm test:run && pnpm build && pnpm preview & pnpm e2e --grep @smoke`

## 7. Environment contract

- [x] 7.1 Create `.env.example` at the project root listing every variable referenced by `docker-compose.yml`, the backend `Settings`, and the frontend build args, with safe defaults or `change-me` placeholders. Include: `ENV`, `LOG_LEVEL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `REDIS_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`, `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `JWT_SECRET=change-me-in-env`, `CORS_ORIGINS`, `VITE_API_URL`, `VITE_ENV`
- [x] 7.2 Add `.env` to the project's existing `.gitignore` (already present — verify)

## 8. CI: GitHub Actions

- [x] 8.1 Create `.github/workflows/backend.yml` triggered on `pull_request` with `paths: ['backend/**', '.github/workflows/backend.yml']` and on `push: { branches: [main] }`. Steps: checkout, setup-python 3.12, install uv, restore cache (`uv-${{ hashFiles('backend/uv.lock') }}`), `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest --cov=app --cov-fail-under=80`
- [x] 8.2 Create `.github/workflows/frontend.yml` triggered on `pull_request` with `paths: ['frontend/**', '.github/workflows/frontend.yml']` and on `push: { branches: [main] }`. Steps: checkout, setup-node 20, corepack enable, `pnpm install --frozen-lockfile`, cache pnpm store keyed on `pnpm-lock.yaml`, cache Playwright browsers, `pnpm lint`, `pnpm typecheck`, `pnpm test:coverage`, `pnpm build`, `pnpm exec playwright install --with-deps chromium`, `pnpm e2e --project=chromium --grep @smoke`
- [x] 8.3 Push the change branch and verify both workflows run green on the PR before requesting review

## 9. Documentation

- [x] 9.1 Create `ai-specs/specs/data-model.md` based on the template, listing the planned entities (`User`, `Project`, `Module`, `Component`, `PriceSnapshot`, `RefreshToken`) with a one-paragraph description per entity and an "Introduced by:" pointer (initially `TBD` or the matching task name from `docs/overview.md`'s backlog table). Explicitly state that column-level schemas are NOT defined in this document yet
- [x] 9.2 Create `ai-specs/specs/development_guide.md` based on the template covering: prerequisites (Docker Desktop, uv, pnpm), clone instructions, `cp .env.example .env`, `docker compose up --build`, the URLs to verify (`http://localhost:8000/api/v1/health`, `http://localhost:5173`), how to view logs per service, where the standards live, and an explicit "Branch protection: set both CI workflows as required status checks on `main` via the GitHub UI" note
- [x] 9.3 Update `ai-specs/specs/api-spec.yml` so it is a minimal valid OpenAPI 3.1 document declaring only the `GET /api/v1/health` endpoint, matching what FastAPI will serve at runtime

## 10. End-to-end verification

- [x] 10.1 On a fresh machine (or after `docker compose down -v && docker system prune`), run `cp .env.example .env && docker compose up --build` and confirm every service reaches healthy/completed: `postgres` (healthy), `redis` (healthy), `migrate` (completed exit 0), `backend` (healthy), `celery_worker` (running 60s+), `celery_beat` (running 60s+), `frontend` (healthy)
- [x] 10.2 Confirm `curl -fsS http://localhost:8000/api/v1/health` returns HTTP 200 with the documented body
- [x] 10.3 Open `http://localhost:5173` and confirm the placeholder shell renders
- [x] 10.4 Run `pre-commit install && pre-commit run --all-files` — all hooks pass
- [x] 10.5 Open a draft PR against `main`; confirm both `backend.yml` and `frontend.yml` workflows run and pass
- [x] 10.6 After PR is green, archive the change with `/opsx:archive bootstrap-runnable-skeleton`
