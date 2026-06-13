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

After seeding components, populate the `/modules` catalogue:

```bash
docker compose run --rm backend python -m app.scripts.seed_modules
```

Inserts ten modules covering all four families (Board · Device · Bundle · Case) and wires the DAG between them (e.g. the Dron bundle contains the BLDC power system + DAQ device + sensor boards, sub-modules and shared leaf components, so the recursive aggregates and "Pertenece a" navigation have something to chew on). Also creates ~36 module-level `stock_events` with kinds `fabricated` (assembly cost lines) and `delivered` (customer shipments, denormalised customer name).

Pass `--reset` to wipe module-level state before re-seeding: deletes `stock_events WHERE module_id IS NOT NULL` (component-level stock events are preserved), `module_children`, then `modules`. Exits with 3 if components aren't already seeded; exits with 2 if `modules` is non-empty without `--reset`.

### Seed sample projects + customers (optional, dev only)

After seeding components and modules, populate the `/projects` catalogue (top of the asset tree):

```bash
docker compose run --rm backend python -m app.scripts.seed_projects
```

Inserts 3 Holded-style customers (`HLD-CUST-001/002/003`) and 5 projects covering every status from the Spanish enum — `Presupuestado` (empty BOM), 2 × `En proceso` (mixed module + component BOMs), `Completado` (with `fecha_entrega_real` set), `Archivado`. Every project carries an `icon` (emoji), `color` (hex), `tags`, and `version`. Also writes ~6 interest links (`{name, url}`) across the projects so the "Enlaces de interés" surface has rows, and ~6 consumption `stock_events` so "Histórico de eventos" is populated.

### Ingest a real component from its MPN (change `ingest-component-from-mpn`)

Instead of typing every field by hand, ingest a component straight from its manufacturer MPN. Given an MPN, the pipeline walks the four supplier APIs, blends the data, infers the internal family, downloads + archives the datasheet PDF, and creates the component fully populated — then the daily sync accumulates its price/stock history.

Two entrypoints share one application service:

```bash
# CLI (local)
docker compose run --rm backend python -m app.scripts.ingest_component NE555P \
  --ubicacion G-T-23 --stock-inicial 100 --holded-id HLD-NE555

# CLI (prod — one-off Container App Job on the backend image)
az containerapp job start -n caj-ada-asm-prod-migrate -g rg-ada-asm-prod \
  --command python -m app.scripts.ingest_component NE555P   # or a dedicated ingest job

# API
POST /api/v1/components/ingest   {"mpn":"NE555P","ubicacion":"G-T-23"}
```

The response (and the CLI output) carries an **IngestionReport**: which suppliers contributed, the inferred family (or `needs_review`), the datasheet outcome (`archived`/`link_only`/`none`), per-table counts, and warnings.

**Family rules.** Inference maps each supplier's category signal to one of the nine internal families via the `component_family_rules` seed table (stable DigiKey/TME `category_id`, Farnell HS `tariff_prefix`, Mouser localized `name_keyword`). Unmapped categories leave the family empty + `needs_review` and are logged (`family_inference.unmapped …`) — grow the table with an `INSERT` (no code deploy):

```sql
INSERT INTO component_family_rules (supplier, match_type, match_value, family, confidence)
VALUES ('digikey', 'category_id', '<leaf id>', 'Sensores', 100);
```

**Datasheet storage env (cloud only).** `DATASHEET_STORAGE_ACCOUNT_URL` (e.g. `https://<acct>.blob.core.windows.net`) + `DATASHEET_CONTAINER=datasheets` select the Azure Blob driver; the backend reads/writes via its managed identity (Storage Blob Data Contributor). Unset → filesystem driver at `DATASHEET_LOCAL_ROOT` (local dev). Datasheet archival is best-effort and never blocks component creation.

Pass `--reset` to wipe (in order) `stock_events WHERE project_id IS NOT NULL`, `project_children`, `projects`, and `customers` before re-seeding (modules + components survive). The `project_interest_links` rows are cascaded by the FK on `project_children → projects`, so they're wiped automatically. Exits with 3 if components or modules aren't seeded yet; exits with 2 if `projects` is non-empty without `--reset`.

#### Project status enum

The `projects.status` enum is in Spanish to match the FE labels verbatim — no translation layer in either direction:

`Presupuestado` · `Esperando` · `En proceso` · `Completado` · `Archivado`

Soft-delete (`DELETE /api/v1/projects/{id}`) transitions to `Archivado`. The PATCH endpoint auto-fills `fecha_entrega_real` with today's date when the status transitions to `Completado` and the request body does not provide an explicit value.

### Env: `HOLDED_BASE_URL`

The `Customer` entity is an id-link to Holded; the FE builds the customer URL as `${HOLDED_BASE_URL}/contact/{holded_id}` unless the row provides an explicit `holded_url` override.

- **Default**: `https://app.holded.com`.
- **Override**: set `HOLDED_BASE_URL` in `.env`.
- **Surfaced to the FE**: `GET /api/v1/config` returns `{holded_base_url}`; the FE caches it via TanStack Query with a 10-minute `staleTime`.

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

## 8b. Supplier sync (change `supplier-sync`)

The backend monitors stock + prices across 5 distributors (Mouser, DigiKey, TME, Farnell, RS Online). A Celery Beat job hits each enabled supplier daily and a synchronous `/components/lookup?mpn=` endpoint pre-fills the new-component form.

### Environment variables

| Var | Purpose | Default / shape |
|---|---|---|
| `MOUSER_API_KEY` | Mouser Search API key. Whitelist your egress public IP at `mouser.com/api-hub/` when applying. | — |
| `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET` | OAuth2 client credentials from `developer.digikey.com`. Enable Product Information V4 on the app. | — |
| `DIGIKEY_OAUTH_TOKEN_URL` | Token endpoint. | `https://api.digikey.com/v1/oauth2/token` |
| `TME_TOKEN` / `TME_APP_SECRET` | **V2** uses HTTP Basic auth: `TME_TOKEN` is the 50-character string (Basic-auth username), `TME_APP_SECRET` is the 20-character string (password). The naming on TME's portal is misleading — what they call "Application secret" is the password here. | — |
| `FARNELL_API_KEY` / `FARNELL_STORE_ID` | element14 Search API. Store ID drives the currency: `es.farnell.com` → EUR, `uk.farnell.com` → GBP (auto-converted via ECB FX). | `es.farnell.com` |
| `RS_API_KEY` | Pending — RS does not self-serve. Email your RS commercial rep to request an App ID. | — |
| `SUPPLIER_SYNC_ENABLED_SUPPLIERS` | Comma-separated supplier codes that may be queried. | `mouser,digikey,tme,farnell` (RS off until credentials arrive) |
| `SUPPLIER_LOOKUP_PRIORITY` | Order in which `/components/lookup` walks suppliers. Higher priority wins on overlapping fields. | `mouser,digikey,tme,farnell,rs` |
| `SUPPLIER_LOOKUP_CACHE_TTL_SECONDS` | Redis cache TTL for `/components/lookup`. | `900` |
| `SUPPLIER_SYNC_DAILY_HOUR_UTC` | Beat schedule hour for the daily sync. | `3` |

A supplier ships disabled if it is **absent from `SUPPLIER_SYNC_ENABLED_SUPPLIERS`** OR its credentials are not present in `.env`. The registry silently skips disabled suppliers (no crash) and logs an INFO line.

### Inspecting and triggering syncs

```bash
# List the most recent sync runs (admin-only, requires bearer token):
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/supplier-sync/runs?limit=20"

# Drill into one run's per-component errors:
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/supplier-sync/runs/<run_uuid>/errors"

# Fire an ad-hoc sync for one supplier (returns 202 with `run_id` + `task_id`):
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/supplier-sync/runs?supplier=mouser"
```

### Adapter onboarding — where to fetch credentials

| Supplier | Portal | Auth model | Friction |
|---|---|---|---|
| Mouser | `mouser.com/api-hub/` | API key in query string; whitelist egress IP | 🟢 ~5 min (key by email) |
| TME | `developers.tme.eu` (needs existing tme.eu customer account) | V2 OAuth2 client_credentials via HTTP Basic | 🟢 ~10 min (uses 600s temporary token from www.tme.eu) |
| Farnell / element14 | `partner.element14.com` | API key in query string (`callInfo.apiKey`) | 🟡 ~15 min (self-serve) |
| DigiKey | `developer.digikey.com` | OAuth2 client_credentials | 🟡 ~30-45 min (Sandbox → Production promote) |
| RS Online | not self-serve — email RS commercial rep | App ID in header | 🔴 days |

### Lookup endpoint

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/components/lookup?mpn=NE555P"
```

Walks the enabled suppliers in priority order, merges fields progressively (empty strings from a higher-priority supplier are treated as missing so the next supplier can fill the gap), and caches the result in Redis for 15 minutes. Pass `&force_refresh=true` to bypass.

## 8c. Cloud deployment (Azure)

The change `cloud-deployment-azure` introduced the Azure-hosted production environment. Everything lives in one Azure tenant under `westeurope`.

### Topology

```
                ┌─ ada.tierra.audio ────────► Azure Static Web App (React SPA)
internet ──────►│
                └─ api.ada.tierra.audio ────► Azure Container App (FastAPI backend)
                                              │
                                              ├─► Azure Container App (Celery worker)
                                              ├─► Container App Job: caj-ada-asm-<env>-beat-cron (KEDA cron 03:00 UTC daily)
                                              ├─► Container App Job: caj-ada-asm-<env>-migrate (deploy-gated)
                                              └─► Container App Job: caj-ada-asm-<env>-seed-admin (one-shot)

                Postgres Flexible Server  ◄── all backend + worker + jobs
                Azure Cache for Redis     ◄── broker, rate limit, FX cache, lookup cache
                Key Vault                 ◄── all secrets, RBAC, soft-delete + purge
                Application Insights      ◄── traces, RUM, logs, dashboard, 5xx alert
```

### IaC + deploy

- Templates live under [`infra/azure/`](../../infra/azure/) — see its [README](../../infra/azure/README.md) for the layout, costs, and naming convention.
- All resources are deployed via Bicep from `infra/azure/main.bicep`, parameterised by `dev` or `prod`.
- Deploys run from GitHub Actions via OIDC Workload Identity Federation — **no long-lived service principal secrets** are stored in GitHub Secrets. The three deploy workflows are:
  - [`.github/workflows/deploy-backend.yml`](../../.github/workflows/deploy-backend.yml) — runs on push to `main` touching `backend/**`.
  - [`.github/workflows/deploy-frontend.yml`](../../.github/workflows/deploy-frontend.yml) — runs on push to `main` touching `frontend/**`.
  - [`.github/workflows/deploy-infra.yml`](../../.github/workflows/deploy-infra.yml) — manual `workflow_dispatch` ONLY.

### Container Registry

- Images live in a **per-environment Azure Container Registry** (Basic SKU):
  - dev → `acradaasmdev.azurecr.io/ada-asm-backend:<sha>`
  - prod → `acradaasmprod.azurecr.io/ada-asm-backend:<sha>` (created when prod is bootstrapped).
- Container Apps + Jobs pull via their **system-assigned managed identity**, which holds the `AcrPull` role on the per-env ACR scope. **No PAT, no Key Vault secret, no `registries[].passwordSecretRef`** — `registries[].identity: 'system'` only.
- The deploy UAMI (`id-deploy-ada-asm-<env>`) holds `AcrPush` on the same ACR scope. The GitHub workflow authenticates via OIDC (`azure/login@v2`) and then `az acr login --name acradaasm<env>` before `docker push`.
- Role grants are wired in Bicep:
  - `AcrPull` — created inside `infra/azure/modules/container_apps.bicep` (backend + worker) and `infra/azure/modules/container_jobs.bicep` (migrate + seed-admin + beat-cron). Lives in those modules because Bicep requires the role-assignment `name` expression to be calculable from same-module resources.
  - `AcrPush` — created inside `infra/azure/modules/identity.bicep` for the deploy UAMI.
- The previous GHCR pull path (`ghcr.io/tierraaudio/ada-asm-backend` + Key Vault `ghcr-pull-token`) was retired in change `pivot-ghcr-to-acr` after persistent auth quirks during dev bootstrap (org-scoped PAT permissions are non-deterministic; public-visibility flips don't propagate reliably).

### Env-var differences vs. local

| Local (`.env`) | Cloud (Key Vault → Container Apps) |
| --- | --- |
| `JWT_SECRET=change-me-in-env` | `secretRef:jwt-secret` |
| `DATABASE_URL=postgresql+asyncpg://ada_asm:ada_asm@postgres:5432/ada_asm` | `secretRef:database-url` (with `?ssl=require` on the Azure FQDN) |
| `CELERY_BROKER_URL=redis://redis:6379/0` | `secretRef:celery-broker-url` — `azurestoragequeues://{account key}@{account}.queue.core.windows.net`. The broker rides Azure Storage Queues (HTTP) because the CAE internal TCP ingress proved unreliable for `redis://` (June 2026: healthy Redis, TCP connect timeouts from every client). `CELERY_RESULT_BACKEND` must NOT be set in cloud: results are disabled app-side and Celery would crash trying to use the `azurestoragequeues://` scheme as a result backend |
| *(unset — falls back to `CELERY_BROKER_URL`)* | `REDIS_CACHE_URL=redis://ca-redis-<env>...:6379/0` — app caches (lookup/FX/rate-limit) stay on the self-hosted Redis Container App; all consumers fail open, so an unreachable Redis only costs performance, never availability |
| Supplier API keys plaintext in `.env` | `secretRef:<supplier>-*-key` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` (absent → observability is no-op) | `secretRef:app-insights-connection-string` |
| `ENVIRONMENT_NAME=local` | `ENVIRONMENT_NAME=dev` or `prod` |

### Runbooks

- [DNS cutover](../../infra/azure/RUNBOOK_DNS_CUTOVER.md) — the one-time procedure for moving `ada.tierra.audio` from the legacy `134.0.10.173` redirect to the new Azure infra.
- [Secret rotation](../../infra/azure/RUNBOOK_SECRET_ROTATION.md) — per-secret rotation procedures with concrete `az` commands.
- [Incident response](../../infra/azure/RUNBOOK_INCIDENT_RESPONSE.md) — what to do when the 5xx alert fires.

### Celery Beat is gone

The change `cloud-deployment-azure` REMOVED the `celery_beat` container from `docker-compose.yml`. The daily supplier sync is now invoked by:

- **Cloud**: a KEDA cron Container App Job at 03:00 UTC.
- **Local**: `make daily-sync` (calls `python -m app.scripts.cron_run_daily_sync`).

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
