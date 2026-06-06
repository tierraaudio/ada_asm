<!-- BEGIN_ENRICHED_USER_STORY -->
# Enriched User Story

design-linked: false
scope:
  backend: true
  frontend: true
source: Manual
reference: N/A — decided in chat conversation 2026-06-05 (option D, all-Azure, App Insights, `ada.tierra.audio`)

## Title

Cloud deployment on Azure — production-ready hosting for the FastAPI + Celery backend, the React/Vite frontend, and the Postgres/Redis data plane under `ada.tierra.audio` + `api.ada.tierra.audio`, with App Insights observability, deploy-time migrations, and Infrastructure-as-Code via Bicep

## Problem / Context

ada_asm has only ever run via `docker compose up` on a developer laptop. There is no production environment, no managed credentials, no observability beyond stdout logs, no automated deploys, no TLS, no public domain wiring. Every secret in `.env` is committed-style (file on disk, no rotation), JWT secret is the literal placeholder `change-me-in-env`, CORS hardcodes `localhost:5173`, and migrations run inside a one-shot Docker service that's coupled to the compose lifecycle.

The team has an existing Azure tenant and wants to use it for everything (one bill, one identity, one console). The DNS for `tierra.audio` is already delegated to Azure DNS (NS records confirmed pointing at `ns*.azure-dns.{com,net,org,info}`), so subdomain work is Azure-only — CDmon (the registrar) is not in the operational path. `ada.tierra.audio` currently resolves to `134.0.10.173` (legacy redirect to tierraaudio.com) and needs to be cleaned up before cutover.

The chosen topology — agreed in the 2026-06-05 discussion as "Opción D" — is all-in Azure: Container Apps for compute, Postgres Flexible Server for DB, Cache for Redis for the broker/cache, Static Web Apps for the SPA, Key Vault for secrets, Application Insights for traces/logs/metrics, KEDA cron trigger to replace Celery Beat.

## Desired Outcome

An operator with the credentials in `.env`-equivalent (Azure Key Vault) can:

- Run `bicep deploy` (or the equivalent `az deployment group` command) and provision the whole stack from scratch.
- Push to `main` and see GitHub Actions build the backend + frontend images, push to GitHub Container Registry, and deploy to the running Container Apps environment with blue/green rollback available.
- Open `https://ada.tierra.audio` in a browser, see the SPA load over TLS, authenticate, and call the backend at `https://api.ada.tierra.audio/api/v1/*`.
- Inspect end-to-end traces, structured logs, and runtime metrics in Application Insights, correlated by `traceparent` between the FE and BE.
- Trigger an ad-hoc Mouser sync from the admin UI and see it appear in `supplier_sync_runs` within seconds.
- Rotate the JWT secret by updating Key Vault — the Container App revisions pick it up without code redeploy.

## Acceptance Criteria (raw)

### Infrastructure as Code (Bicep)

A new top-level directory `infra/azure/` SHALL host the Bicep templates. The deployment SHALL be parameterised by environment (`dev` / `prod`) so the same templates work for both.

Resources provisioned:

- **Resource Group**: `rg-ada-asm-<env>` in `westeurope`.
- **Log Analytics Workspace** + **Application Insights**: `log-ada-asm-<env>` / `appi-ada-asm-<env>`. PerGB2018 SKU, 30-day retention on dev, 90-day on prod.
- **Container Apps Environment**: `cae-ada-asm-<env>`, internal load balancer disabled (public ingress), workload profile `Consumption` (no dedicated nodes — scale-to-zero).
- **Azure Container Registry**: NOT provisioned. Images live in **GitHub Container Registry** (`ghcr.io/tierraaudio/ada-asm-backend`, `ghcr.io/tierraaudio/ada-asm-frontend`) — saves ~$5/month and avoids the round-trip.
- **Container App: backend** (`ca-ada-asm-backend-<env>`):
  - Image: `ghcr.io/tierraaudio/ada-asm-backend:<sha>`
  - Min replicas: 0 (dev) / 1 (prod); Max: 3 (dev) / 5 (prod).
  - CPU: 0.5 vCPU / 1 GB RAM (dev) ; 1 vCPU / 2 GB RAM (prod).
  - Ingress: public, port 8000, transport `http`, custom domain `api.ada.tierra.audio` with managed cert.
  - HTTP scale rule: `concurrent_requests >= 50`.
  - Health probe: `GET /api/v1/health`.
  - Revision mode: `multiple` (blue/green via traffic split).
- **Container App: celery_worker** (`ca-ada-asm-worker-<env>`):
  - Same image as backend, command override `["celery","-A","app.infrastructure.celery_app","worker","-l","info"]`.
  - Ingress disabled (worker is queue-driven).
  - KEDA scale rule: Redis list length (`celery` queue) — min 0, max 3.
- **Container App Job: celery_beat_cron** (`caj-ada-asm-beat-<env>`):
  - **Replaces** the existing `celery_beat` container entirely.
  - Trigger: KEDA cron schedule `0 3 * * *` (03:00 UTC daily).
  - Command: `python -m app.scripts.cron_run_daily_sync` (new entry point that calls `run_daily_sync()` synchronously and exits) — Beat is no longer a long-running process.
  - Max 1 concurrent execution.
- **Container App Job: migrate** (`caj-ada-asm-migrate-<env>`):
  - Trigger: manual / GitHub Actions invocation pre-revision.
  - Command: `alembic upgrade head`.
  - Replaces the `migrate` service in compose for production.
- **Azure Database for PostgreSQL — Flexible Server** (`pg-ada-asm-<env>`):
  - SKU: `B_Standard_B1ms` (1 vCPU / 2 GB RAM) on dev; `B_Standard_B2s` on prod.
  - Postgres 16, storage 32 GB GP, geo-redundant backups on prod, locally-redundant on dev.
  - Extensions enabled at creation time: `pgcrypto`, `ltree`, `pg_stat_statements`.
  - High availability disabled (cost). Add later if SLAs demand it.
  - Public network access disabled; private endpoint inside the Container Apps environment vnet, OR firewall rule allowing the ACA outbound IPs.
- **Azure Cache for Redis** (`redis-ada-asm-<env>`):
  - SKU: `Basic C0` (250 MB, no SLA) on dev; `Standard C1` (1 GB, 99.9 SLA) on prod.
  - Non-SSL port disabled (`rediss://` only).
  - Lua scripts supported by default — no extra config.
- **Static Web App** (`stapp-ada-asm-<env>`):
  - Free tier on dev, Standard on prod.
  - GitHub Actions build pipeline auto-generated by the SWA resource.
  - Custom domain `ada.tierra.audio` with managed cert.
- **Key Vault** (`kv-ada-asm-<env>`):
  - Soft-delete + purge protection enabled.
  - Secrets seeded by the Bicep deploy: `jwt-secret`, `postgres-password`, `redis-key`, `mouser-api-key`, `digikey-client-id`, `digikey-client-secret`, `tme-token`, `tme-app-secret`, `farnell-api-key`, `rs-api-key`, `app-insights-connection-string`.
  - RBAC mode (NOT access policies). Container Apps system-assigned managed identities granted `Key Vault Secrets User`.
- **DNS records** (Azure DNS zone `tierra.audio`):
  - `ada` → CNAME → `<swa>.azurestaticapps.net`.
  - `api.ada` → CNAME → `<aca-backend>.azurecontainerapps.io`.
  - `asuid.ada`, `asuid.api.ada` → TXT records emitted by Azure for managed-cert validation.
  - Pre-existing `ada` A record pointing at `134.0.10.173` (legacy tierraaudio.com redirect — confirmed disposable) DELETED.

### Backend code hardening

- `CORS_ORIGINS` reads a comma-separated list from env (already does) AND the default `.env.example` is updated to `https://ada.tierra.audio` for prod. The local `.env` keeps localhost values.
- `JWT_SECRET` is sourced via a Key Vault reference in Container Apps (`secretref:jwt-secret`), NOT from a hardcoded env literal.
- `DATABASE_URL` accepts the Azure-style URL `postgresql+asyncpg://user:pass@host.postgres.database.azure.com:5432/db?ssl=require`. Tests verify SSL is required when `sslmode=require` is in the URL.
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` accept `rediss://` URLs (TLS).
- New module `app/infrastructure/observability.py`:
  - Initialises OpenTelemetry SDK with the Azure Monitor OTLP exporter when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set.
  - Instruments FastAPI (via `opentelemetry-instrumentation-fastapi`), httpx, SQLAlchemy, and Celery.
  - Adds a structlog processor that pulls the current trace_id / span_id into every log record so App Insights correlates them.
  - No-op when the connection string is absent (local dev unchanged).
- New env vars: `APPLICATIONINSIGHTS_CONNECTION_STRING`, `ENVIRONMENT_NAME` (used as the `service.environment` resource attribute).
- New script `app/scripts/cron_run_daily_sync.py` — runs `run_daily_sync()` synchronously inside `asyncio.run`, exits 0 on success / non-zero on failure. Used by the KEDA cron job to replace Celery Beat.

### Frontend code hardening

- `VITE_API_URL` default in `.env.example` and `docker-compose.yml` stays at `http://localhost:18000`, but the production build SHALL use `https://api.ada.tierra.audio` injected at build time by the SWA pipeline.
- New `staticwebapp.config.json` at repo root sets:
  - Fallback route to `/index.html` for SPA routing.
  - Security headers: `Content-Security-Policy` (allowing the API host + Application Insights), `Strict-Transport-Security`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
  - Mime-type overrides for `.wasm` / `.json` if needed.
- New module `frontend/src/lib/telemetry.ts`:
  - Uses `@microsoft/applicationinsights-web` with connection string from `import.meta.env.VITE_APP_INSIGHTS_CONNECTION_STRING`.
  - Automatic page-view tracking, XHR/fetch instrumentation, RUM.
  - Distributed tracing enabled — the `traceparent` header is propagated to `api.ada.tierra.audio`.
  - No-op when the connection string is absent.

### CI/CD (GitHub Actions)

Three new workflows under `.github/workflows/`:

- `deploy-backend.yml`:
  - Triggers: push to `main` that touches `backend/**` OR manual `workflow_dispatch`.
  - Steps: ruff + mypy + pytest (80% gate) → build Docker image → push to GHCR → run `caj-ada-asm-migrate-<env>` Container App Job and wait → update `ca-ada-asm-backend-<env>` and `ca-ada-asm-worker-<env>` to the new image tag with `--revision-suffix=<sha>` → set traffic split to 100% on the new revision.
  - Federated identity (OIDC) — no service principal client secrets in GitHub Secrets.
- `deploy-frontend.yml`:
  - Triggers: push to `main` that touches `frontend/**` OR manual `workflow_dispatch`.
  - Steps: pnpm install → vitest (80% gate) → vite build with `VITE_API_URL=https://api.ada.tierra.audio` and `VITE_APP_INSIGHTS_CONNECTION_STRING=<secret>` → SWA deploy via the SWA-provided action.
- `deploy-infra.yml`:
  - Manual `workflow_dispatch` only.
  - Steps: `az deployment group validate` → `az deployment group what-if` (preview) → on manual approval, `az deployment group create`.
  - Templates: `infra/azure/main.bicep` + per-resource modules.

### DNS migration runbook

A new doc `infra/azure/RUNBOOK_DNS_CUTOVER.md` describes:

1. Before cutover: delete the existing `ada.tierra.audio → 134.0.10.173` A record in the Azure DNS zone (confirmed disposable legacy redirect).
2. Apply the Bicep template — provisions the CNAMEs to ACA + SWA.
3. Wait for managed cert issuance (Azure polls the `asuid` TXT records — typically 5-15 min).
4. Verify `https://ada.tierra.audio` and `https://api.ada.tierra.audio/api/v1/health` return 200.
5. Rollback: re-apply previous Bicep state via `what-if` review.

### Observability

- `Application Insights` collects: backend HTTP request traces, SQL queries (sampled), httpx calls to supplier APIs (sampled to 10% in prod), Celery task duration, custom events for `supplier_sync_runs.status` transitions, frontend page views + custom RUM events.
- A pre-built dashboard `dashboard-ada-asm-<env>.json` lives in `infra/azure/` and is deployable via Bicep. Default tiles: backend p50/p95/p99 latency, error rate, supplier-sync success rate per day, Redis cache hit ratio on the `/components/lookup` endpoint.
- One alert rule: backend HTTP 5xx rate > 5% over 5 min → email to `ops@tierra.audio`.

### Initial admin seed

The existing CLI script `python -m app.scripts.seed_admin` is not viable in a non-interactive cloud environment. Add:

- A new Container App Job `caj-ada-asm-seed-admin-<env>` that runs the seed script with email/password supplied via Key Vault references (`seed-admin-email`, `seed-admin-password`). Triggered manually post-first-deploy.
- The script remains backwards-compatible — it just reads `--email` / `--password` from env vars now if CLI args are absent.

### Documentation

- `ai-specs/specs/development_guide.md`: add §11 "Cloud deployment (Azure)" with a high-level diagram (text), env-var differences vs. local, link to runbooks.
- `ai-specs/specs/backend-standards.mdc`: add "Cloud configuration" section noting Key Vault references, SSL DB connection requirement, OpenTelemetry conventions.
- `infra/azure/README.md`: how to provision a fresh env, how to inspect logs, how to rotate secrets, cost expectations.
- Update `CLAUDE.md` (root + `ada_asm/`) to mention the new `infra/azure/` directory.

### Tests

- Backend unit: settings parsing of `rediss://` and `sslmode=require` URLs; observability module is a no-op when connection string is absent.
- Backend integration: existing 246 tests must remain green against an SSL-required Postgres URL (we already use asyncpg, no change needed beyond `ssl=require` param).
- Frontend: telemetry module is a no-op when env var is absent.
- Infra: `infra/azure/main.bicep` passes `az deployment group validate` in CI.

## Constraints / Notes

- **No Vercel.** Even though we considered it for the FE, the decision is all-Azure.
- **No multi-region failover** in scope. The whole stack is in `westeurope`. Disaster recovery is "restore Postgres from backup, re-apply Bicep". If we ever go multi-region, that's a separate change.
- **Cost target**: ~€40/month for prod, near-zero for dev when idle (scale-to-zero on worker + backend min=0 on dev).
- **No real auto-scaling tuning** — defaults are reasonable; tuning is deferred until we have actual load data.
- **Beat is deleted, not migrated.** The KEDA cron job replaces it. This is intentional simplification.
- **`ada.tierra.audio` legacy redirect to `134.0.10.173`** is disposable per user confirmation — delete it as part of the cutover.
- **CDmon stays as-is** — registrar only, no DNS records to manage there. The Azure DNS zone is the single source of truth.
- All user-facing copy in Spanish (matching the rest of the app). All code/comments/log strings in English.

<!-- END_ENRICHED_USER_STORY -->
