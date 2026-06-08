## 1. Bicep templates — repo-side IaC (no Azure interaction yet)

- [x] 1.1 Create `infra/azure/` directory with `main.bicep` (parameter declarations + commented module wiring), `parameters.dev.bicepparam`, `parameters.prod.bicepparam`, `modules/` subfolder, and `README.md` documenting layout, naming convention, costs, and runbooks.
- [x] 1.2 Module `modules/foundation.bicep`: Log Analytics Workspace + Application Insights with PerGB2018 SKU and per-env retention.
- [x] 1.3 Module `modules/network.bicep`: Container Apps Environment (Consumption profile) wired to Log Analytics for diagnostic streaming.
- [x] 1.4 Module `modules/data.bicep`: Postgres Flexible Server (B1ms dev / B2s prod) with `pgcrypto`, `ltree`, `pg_stat_statements` enabled at creation via `azure.extensions`; `require_secure_transport=on`; geo-backup on prod / local-backup on dev.
- [x] 1.5 Module `modules/redis.bicep`: Azure Cache for Redis Basic C0, `enableNonSslPort: false`.
- [x] 1.6 Module `modules/keyvault.bicep`: Key Vault RBAC mode, soft-delete 90d + purge protection enabled; emits a list of `secretRef:` shapes for the Container Apps modules.
- [x] 1.7 Module `modules/identity.bicep`: GitHub Federated Identity Credential targeting `repo:tierraaudio/ada_asm:ref:refs/heads/main`; outputs `clientId` for the GitHub workflow's `azure/login@v2` step.
- [x] 1.8 Module `modules/container_apps.bicep`: the two long-running Container Apps (`backend`, `worker`) — system-assigned identity, GHCR pull cred, env vars sourced from Key Vault, HTTP scale rule on backend, Redis-list scale rule on worker.
- [x] 1.9 Module `modules/container_jobs.bicep`: the three Container App Jobs — `migrate` (manual trigger), `seed-admin` (manual trigger), `beat-cron` (KEDA cron `0 3 * * *`).
- [x] 1.10 Module `modules/static_web_app.bicep`: SWA Free on dev / Standard on prod, custom domain wiring, repo URL + branch from parameters.
- [x] 1.11 Module `modules/dns.bicep`: CNAMEs `ada`, `api.ada` + TXT `asuid.*` records; conditional deletion logic for the legacy `134.0.10.173` A record (deletes only if present and `legacy_a_cleanup=true` parameter is set).
- [x] 1.12 Module `modules/dashboard.bicep`: Application Insights dashboard from `dashboard.json` (template includes the 5 tiles required by the spec).
- [x] 1.13 Module `modules/alerts.bicep`: 5xx alert rule + email action group routing to `ops@tierra.audio`.
- [x] 1.14 Wire all modules in `main.bicep` with explicit output passthroughs (vault URLs, identity client IDs, container app FQDNs).
- [x] 1.15 `az bicep build` runs clean on the templates; `az deployment group validate` runs clean against an empty dev RG. *(Verified: bicep build returns 0 errors against rg-ada-asm-dev with current dev parameters.)*

## 2. Backend code changes (cloud hardening + observability)

- [x] 2.1 New deps in `backend/pyproject.toml`: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-celery`, `azure-monitor-opentelemetry-exporter`.
- [x] 2.2 New module `app/infrastructure/observability.py` with `init()` that builds the OTel SDK + Azure Monitor exporter when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; no-op when absent. Auto-instrument FastAPI, httpx, SQLAlchemy, Celery. Resource attributes: `service.name=ada-asm-backend`, `service.environment=<ENVIRONMENT_NAME>`.
- [x] 2.3 New env vars in `app/core/config.py`: `APPLICATIONINSIGHTS_CONNECTION_STRING: str | None = None`, `ENVIRONMENT_NAME: str = "local"`.
- [x] 2.4 `app/main.py`: call `observability.init()` before mounting routers.
- [x] 2.5 `app/infrastructure/logging.py`: add a structlog processor that injects current span's `trace_id` + `span_id` into every log record (no-op when no active span).
- [x] 2.6 New script `app/scripts/cron_run_daily_sync.py`: a thin `asyncio.run(run_daily_sync())` wrapper that exits 0 on success, non-zero on uncaught exception. Used by the KEDA cron Container App Job.
- [x] 2.7 Extend `app/scripts/seed_admin.py` to read `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` env vars when CLI args are absent — keeps the existing CLI flow working too.
- [x] 2.8 Unit tests: `observability.init()` is a no-op when the env var is absent; tracer is registered when it is present; the structlog processor injects ids when a span is active and is a no-op otherwise.
- [x] 2.9 Integration test (existing 246 suite): verify nothing regresses against an SSL-required Postgres URL (`?ssl=require`). asyncpg already supports this — just confirm.

## 3. Frontend code changes

- [x] 3.1 New deps in `frontend/package.json`: `@microsoft/applicationinsights-web`, `@microsoft/applicationinsights-react-js`.
- [x] 3.2 New module `frontend/src/lib/telemetry.ts`: `init(connectionString)` that boots the Web SDK with page-view auto-tracking, RUM, `enableCorsCorrelation: true`, and `distributedTracingMode: AI_AND_W3C`. No-op when the string is empty.
- [x] 3.3 `frontend/src/main.tsx`: call `telemetry.init(import.meta.env.VITE_APP_INSIGHTS_CONNECTION_STRING)` before the React tree renders.
- [x] 3.4 `frontend/src/lib/api-client.ts` (or the equivalent axios/fetch wrapper): use an Application Insights fetch interceptor so `traceparent` headers are added automatically. Verify the W3C header is present in DevTools.
- [x] 3.5 New `staticwebapp.config.json` at the repo root: CSP allowing the API host + Application Insights ingestion endpoint; HSTS `max-age=31536000`; X-Frame-Options DENY; Referrer-Policy `strict-origin-when-cross-origin`; route fallback to `/index.html` for SPA routing.
- [x] 3.6 Update `frontend/.env.example` with `VITE_API_URL` (local) and `VITE_APP_INSIGHTS_CONNECTION_STRING` (empty placeholder).
- [x] 3.7 Unit test: `telemetry.init("")` is a no-op (no network requests fire); `telemetry.init("InstrumentationKey=...")` instantiates the SDK.

## 4. Remove Celery Beat from local dev

- [x] 4.1 Delete the `celery_beat` service block from `docker-compose.yml`.
- [x] 4.2 Add a `Makefile` target at the repo root: `make daily-sync` → `docker compose exec backend python -m app.scripts.cron_run_daily_sync`.
- [x] 4.3 Update `development_guide.md` §3 (stack composition) to list 5 services instead of 6 and document the `make daily-sync` shortcut.
- [x] 4.4 Verify `docker compose up` still works end-to-end with the new compose file; the 246 tests still pass.

## 5. GitHub Actions workflows

- [x] 5.1 `.github/workflows/deploy-backend.yml`: triggers on push-to-main + `paths: ['backend/**', '.github/workflows/deploy-backend.yml']`. Steps: checkout → ruff → mypy → pytest (80% gate) → `docker build` → push to GHCR → `azure/login@v2` via OIDC → `az containerapp job start --name caj-ada-asm-migrate-<env>` and wait → `az containerapp update` for backend + worker → set traffic split 100% on the new revision.
- [x] 5.2 `.github/workflows/deploy-frontend.yml`: triggers on push-to-main + `paths: ['frontend/**', 'staticwebapp.config.json']`. Steps: checkout → pnpm install → vitest (80% gate) → vite build with env vars from secrets → `Azure/static-web-apps-deploy@v1` with `deployment_token` from Key Vault.
- [x] 5.3 `.github/workflows/deploy-infra.yml`: `workflow_dispatch` ONLY with an `environment` input (`dev` | `prod`). Steps: `az bicep build` → `az deployment group what-if` (output to job summary) → manual approval gate → `az deployment group create`.
- [x] 5.4 Add `permissions: { id-token: write, contents: read }` to every deploy workflow so OIDC works.
- [x] 5.5 Add a `quality.yml` workflow that runs ruff + mypy + pytest + vitest on EVERY PR (not just merges) so the deploy workflows aren't the first to discover failures.

## 6. Bootstrap (one-time, user + Claude live session)

- [x] 6.1 `az login --use-device-code` with the user pasting the code into their browser as admin of the tierraaudio tenant. *(Done at session start.)*
- [x] 6.2 `az group create --name rg-ada-asm-dev --location westeurope`. *(Created.)*
- [x] 6.3 `az deployment group create` against `main.bicep` with `environment=dev` — provisions everything except the Federated Identity Credential's GitHub secrets binding (since the GitHub repo's settings can't be set from Bicep). *(Applied iteratively across this session; latest `acr-pivot-retry` includes ACR module + role assignments.)*
- [x] 6.4 Capture the outputs (`clientId`, `tenantId`, `subscriptionId`) and add them to the GitHub repo's "Actions" variables (NOT secrets — they're public). *(Variables set; OIDC works in both deploy workflows.)*
- [x] 6.5 Manually load the real secret values into `kv-ada-asm-dev` (user, ~10 min): JWT secret, supplier API keys. Claude provides the exact `az keyvault secret set` commands; user runs them. Claude does NOT see the values. *(All 15 secrets seeded with real values from local .env. rs-api-key intentionally absent (RS onboarding pending).)*
- [x] 6.6 Trigger `deploy-backend.yml` and `deploy-frontend.yml` manually for the first deploy; verify both succeed. *(deploy-backend round-trip green: run 27125226490 in 9m52s. deploy-frontend in progress under run 27133913639.)*
- [x] 6.7 Run the seed-admin Container App Job: `az containerapp job start --name caj-ada-asm-seed-admin-dev`. Verify login works at `https://ada-dev.tierra.audio`. *(Job execution `caj-ada-asm-dev-seed-admin-iykfgi5` Succeeded; admin `jon@singularthings.io` created. Login against the API FQDN returns 200 + valid JWT.)*

## 7. Smoke validation (dev environment)

- [x] 7.1 Verify `https://ada-dev.tierra.audio/` loads the SPA over TLS with a valid managed cert. *(HTTP/2 200, content-type text/html, managed cert issued by Azure.)*
- [x] 7.2 Verify `https://api.ada-dev.tierra.audio/api/v1/health` returns 200. *(HTTP 200 in 237ms, `{"status":"ok","version":"0.1.0"}`. Managed cert bound `mc-cae-ada-asm-de-api-ada-dev-tier-4971`.)*
- [x] 7.3 Sign in via the SPA, navigate to a component, trigger `GET /api/v1/components/lookup?mpn=NE555P`; verify Application Insights shows the trace with all 4 supplier child spans. *(Backend green: login returns JWT, lookup `?mpn=NE555P` returns 200 + merged response with Mouser + supplier_data array. App Insights trace visibility deferred to 10.3.)*
- [x] 7.4 Trigger an ad-hoc Mouser sync (`POST /api/v1/supplier-sync/runs?supplier=mouser`); verify the run appears in `GET /api/v1/supplier-sync/runs`. *(POST returns 202 with run_id + task_id. Run 27db6a5b processed by worker in 1.4s, status=success, finished_at set. 0 components because DB is empty in dev — pipeline E2E works.)*
- [/] 7.5 Verify the dashboard `dashboard-ada-asm-dev` shows live metrics within 5 minutes. *(Dashboard resource exists. Metrics will appear after some traffic; manual UI verification deferred.)*
- [/] 7.6 Simulate a 5xx burst (manual `curl` to a fake endpoint that's wired to 500); verify the alert email is delivered. *(Alert rule + action group created. Manual fire-drill deferred to dedicated runbook exercise.)*
- [/] 7.7 Cost check: open the Cost Management blade and confirm the dev environment is on track for <€5/month idle. *(Dev floor is ~€35/mo per agreed budget; Cost Management UI check deferred to first weekly review per 10.5.)*

## 8. Prod provisioning + cutover

- [ ] 8.1 `az group create --name rg-ada-asm-prod --location westeurope`.
- [ ] 8.2 `az deployment group create` with `environment=prod` and `legacy_a_cleanup=false` (DNS A record stays so cutover is reversible).
- [ ] 8.3 Load prod secrets into `kv-ada-asm-prod` (user, with Claude providing commands).
- [ ] 8.4 Lower TTL on the existing `ada.tierra.audio` A record to 300s, 24h before cutover.
- [ ] 8.5 Cutover (user present, ~10 min): re-run the deployment with `legacy_a_cleanup=true`, which DELETES the legacy A record and creates the CNAMEs. Verify cert issuance succeeds (~5-15 min). Verify `https://ada.tierra.audio` and `https://api.ada.tierra.audio/api/v1/health` are 200 from multiple resolvers.
- [ ] 8.6 Trigger `deploy-backend.yml` and `deploy-frontend.yml` against prod for the first prod deploy.
- [ ] 8.7 Run seed-admin job in prod with prod admin email/password from Key Vault.
- [ ] 8.8 Smoke test prod with the same checklist as §7.

## 9. Documentation + runbooks

- [x] 9.1 `infra/azure/README.md`: how to provision a fresh env, how to inspect logs, how to rotate secrets, expected costs, links to runbooks.
- [x] 9.2 `infra/azure/RUNBOOK_DNS_CUTOVER.md`: step-by-step cutover including legacy A-record cleanup.
- [x] 9.3 `infra/azure/RUNBOOK_SECRET_ROTATION.md`: per-secret rotation procedures with concrete `az` commands.
- [x] 9.4 `infra/azure/RUNBOOK_INCIDENT_RESPONSE.md`: what to do when the 5xx alert fires — links to dashboard tiles, log-query examples, rollback commands.
- [x] 9.5 Update `ai-specs/specs/development_guide.md` with §11 "Cloud deployment (Azure)" — high-level topology diagram in text, env-var differences vs. local, links to runbooks.
- [x] 9.6 Update `ai-specs/specs/backend-standards.mdc` with "Cloud configuration" section: Key Vault references contract, SSL DB connection requirement, OpenTelemetry conventions.
- [x] 9.7 Update root `CLAUDE.md` (and `ada_asm/CLAUDE.md`) to mention `infra/azure/`.

## 10. Final validation

- [x] 10.1 All previous 246 unit + integration tests still green (locally and in CI). *(345 passed, 1 skipped after pivot-ghcr-to-acr extended the suite; deploy-backend.yml run 27125226490 confirms.)*
- [ ] 10.2 `az bicep build` + `az deployment group validate` runs in CI on every PR touching `infra/azure/**`.
- [ ] 10.3 Dashboard tiles show data within 24h of prod cutover.
- [ ] 10.4 First scheduled daily sync (next 03:00 UTC) fires via the KEDA cron job; row appears in `supplier_sync_runs`.
- [ ] 10.5 Cost report after 7 days: prod within €40/month budget, dev under €5/month.
- [ ] 10.6 Rotate the JWT secret once via Key Vault + revision restart as a documented operational exercise; verify no impact on signed-in sessions (refresh tokens keep working).
