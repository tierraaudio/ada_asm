## Why

ada_asm has never run outside a developer laptop. There is no production environment, no managed credentials, no observability beyond stdout, no automated deploys, no TLS, no public domain. Every secret is plaintext in `.env`, the JWT secret is the literal placeholder `change-me-in-env`, CORS hardcodes `localhost:5173`, and migrations run inside a one-shot Docker service coupled to the `docker compose` lifecycle. We need to get this into a real cloud environment before anything can be demoed externally or used by anyone other than the developer running the laptop.

The team has an existing Azure tenant (admin: jon@tierra.audio) and wants to consolidate on Azure for procurement + compliance + identity (Entra ID). DNS for `tierra.audio` is already delegated to Azure DNS — the registrar (CDmon) is registrar-only and out of the operational path. The decision is "Opción D" (all-Azure) from the 2026-06-05 conversation: Container Apps for compute, Postgres Flexible Server for DB, Cache for Redis for broker+cache, Static Web Apps for the SPA, Key Vault for secrets, Application Insights for telemetry, KEDA cron to replace Celery Beat.

The win is a production system that costs ~€40/month, deploys from `main` without humans in the loop after the initial bootstrap, has end-to-end traces correlated FE↔BE, and survives the "I closed my laptop" test.

## What Changes

- **NEW** `infra/azure/` directory at the repo root with the full Bicep templates for: Resource Group, Log Analytics + Application Insights, Container Apps Environment, 2 Container Apps (`backend`, `worker`), 3 Container App Jobs (`migrate`, `seed-admin`, `beat-cron` via KEDA), Postgres Flexible Server, Azure Cache for Redis, Static Web App, Key Vault, DNS records, App Insights dashboard.
- **NEW** GitHub Container Registry (`ghcr.io/tierraaudio/ada-asm-backend` + `…-frontend`) as the image registry — no Azure Container Registry, saves €5/month and avoids a round-trip.
- **NEW** Federated Identity Credential (OIDC) between GitHub Actions and Azure so deploys run without service principal secrets.
- **NEW** GitHub Actions workflows (`.github/workflows/`): `deploy-backend.yml`, `deploy-frontend.yml`, `deploy-infra.yml`. Migrations run as a Container App Job pre-revision; traffic flips to the new revision after a healthy probe.
- **NEW** observability module `app/infrastructure/observability.py` — OpenTelemetry SDK wired into Azure Monitor with auto-instrumentation for FastAPI, httpx, SQLAlchemy, Celery. A structlog processor injects `trace_id` / `span_id` into every log record so App Insights correlates them. **NO-OP when `APPLICATIONINSIGHTS_CONNECTION_STRING` is absent** — local development stays unchanged.
- **NEW** frontend telemetry module `frontend/src/lib/telemetry.ts` using `@microsoft/applicationinsights-web`. Page views + RUM + distributed-tracing `traceparent` propagation. No-op locally.
- **NEW** `staticwebapp.config.json` at the repo root setting `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options: DENY`, `Referrer-Policy`, and the SPA fallback to `/index.html`.
- **NEW** `app/scripts/cron_run_daily_sync.py` — a synchronous entry point (`asyncio.run(run_daily_sync())`) invoked by the KEDA cron Container App Job. **Replaces the existing `celery_beat` container entirely** — no long-running Beat process in production.
- **NEW** Container App Job to seed the admin user (`app/scripts/seed_admin.py` extended to read `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` from env when CLI args are absent).
- **NEW** `infra/azure/RUNBOOK_DNS_CUTOVER.md` documenting the cutover including the deletion of the pre-existing `ada.tierra.audio → 134.0.10.173` legacy A record (confirmed by the user as a disposable redirect to tierraaudio.com).
- **MODIFIED** `app/core/config.py` to accept `APPLICATIONINSIGHTS_CONNECTION_STRING` and `ENVIRONMENT_NAME` (both optional, default to None / `"local"`).
- **MODIFIED** `app/main.py` to call `observability.init()` at boot.
- **MODIFIED** `app/infrastructure/logging.py` to add the trace processor.
- **MODIFIED** `frontend/src/main.tsx` to call `telemetry.init()` at boot.
- **MODIFIED** `frontend/src/lib/api-client.ts` (or equivalent) to propagate `traceparent` to the backend.
- **MODIFIED** `.env.example` with the new env vars (commented out so they default to no-op).
- **MODIFIED** `docker-compose.yml` to **REMOVE the `celery_beat` service** — the cron now runs only in Azure via KEDA. Local development gets a manual `make daily-sync` (one-line invoke of the new cron script).
- No change to business logic. No change to existing endpoints. No change to the supplier-sync code beyond the cron entry point.

## Capabilities

### New Capabilities
- `cloud-infrastructure`: Bicep templates + parameter files that provision every Azure resource (Resource Group through DNS records) for `dev` and `prod` environments. Covers the IaC contract and the resource naming convention.
- `cloud-observability`: OpenTelemetry-based observability that pushes traces, logs, and metrics to Application Insights from both the backend (FastAPI + Celery + SQLAlchemy + httpx) and the frontend (Web SDK + RUM). Includes the cross-tier `traceparent` propagation contract.
- `cloud-deploy-pipeline`: The CI/CD contract — federated identity, image build to GHCR, migration job pre-revision, blue/green via Container App revisions, manual approval gate for infra changes. Covers what every push to `main` does.
- `cloud-secret-management`: Key Vault-as-source-of-truth contract — which secrets are stored, which Container Apps reference them, and how rotation happens without code redeploy.

### Modified Capabilities
- `runnable-skeleton`: the existing skeleton's expectation of "all services run under `docker compose`" is extended — Celery Beat is **removed** from compose (cron now lives in Azure). The skeleton still runs the backend, worker, Postgres, Redis, and frontend locally for development; the daily sync is invoked manually via `make daily-sync` in local dev.

## Impact

- **Repo layout**: new top-level `infra/` directory; new `.github/workflows/*.yml` files; new `staticwebapp.config.json` at the root.
- **Backend code**:
  - New: `app/infrastructure/observability.py`, `app/scripts/cron_run_daily_sync.py`.
  - Modified: `app/main.py`, `app/core/config.py`, `app/infrastructure/logging.py`, `app/scripts/seed_admin.py`.
  - New deps: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-celery`, `azure-monitor-opentelemetry-exporter`.
- **Frontend code**:
  - New: `frontend/src/lib/telemetry.ts`, `staticwebapp.config.json`.
  - Modified: `frontend/src/main.tsx`, `frontend/src/lib/api-client.ts`.
  - New deps: `@microsoft/applicationinsights-web`, `@microsoft/applicationinsights-react-js`.
- **Compose**: `docker-compose.yml` loses the `celery_beat` service. No other change.
- **DNS**: the existing `ada.tierra.audio → 134.0.10.173` A record is deleted. Two CNAMEs (`ada` and `api.ada`) plus two `asuid.*` TXT records (Azure managed-cert validation) are created.
- **Cost**: ~€40/month for prod (Postgres B2s ≈ €17, Redis Standard C1 ≈ €40 — DOWNGRADE to Basic C0 ≈ €16 for now since we have no SLA target; revisit when prod sees real traffic). Dev scales to zero on workers; Postgres B1ms + Redis Basic C0 floor ≈ €33/month even when idle.
- **Security**: secrets move from a developer laptop's `.env` file to Azure Key Vault with RBAC + soft-delete + purge protection. JWT secret rotation becomes a Key Vault operation with zero code deploy.
- **Tests**: existing 246 tests must remain green against an SSL-required Postgres URL and a `rediss://` Redis URL. New unit tests for the observability module's no-op-when-absent behaviour. New CI step `az bicep build` + `az deployment group validate` on the Bicep templates.
- **Docs**: `development_guide.md`, `backend-standards.mdc`, new `infra/azure/README.md` and runbooks.
- **No frontend feature changes**. No business logic changes. No supplier-sync changes beyond the cron entry point.
