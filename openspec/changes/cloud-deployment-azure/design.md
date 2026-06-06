## Context

ada_asm is a four-tier app: React/Vite SPA + FastAPI (asyncio) + PostgreSQL 16 + Redis-backed Celery (worker + Beat). Until now it only ran under `docker compose` on a developer laptop. We're deploying it to the team's existing Azure tenant (`tierra.audio` is registered at CDmon but the DNS authority is delegated to Azure DNS — confirmed via `dig NS tierra.audio`).

The decision tree leading to "all-Azure" went through Vercel (no fit for the long-running Celery worker), AWS/GCP (no existing account, no compelling reason to add one), and a hybrid "Azure compute + Neon/Upstash data" option (€10/month cheaper but splits the bill across three providers without buying any feature we need). The final pick is all-in Azure because the account is already paid for, the compliance posture is needed for future enterprise customers, and Azure Container Apps + KEDA cron is genuinely well-suited to our shape — multi-container with a daily cron + queue-driven workers — without the operational overhead of AKS.

Cost target: ~€40/month for prod, near-zero for dev when idle. Postgres + Redis are the only floors that don't scale to zero.

## Goals / Non-Goals

**Goals:**

- A production environment reachable at `https://ada.tierra.audio` (SPA) and `https://api.ada.tierra.audio` (API), with managed TLS certs auto-renewed by Azure.
- A `dev` environment with the same topology that costs <€5/month idle so we can preview risky changes without breaking prod.
- All compute defined as Bicep, every change auditable via git.
- All secrets in Key Vault with RBAC, referenced from Container Apps as `secretref:`. Rotation = update the secret, restart the revision. No code changes, no redeploy.
- GitHub Actions deploys via OIDC federated identity — no service principal client secrets persisted anywhere.
- End-to-end tracing from frontend page-view to backend SQL query, correlated by W3C `traceparent`, visible in Application Insights without extra wiring per request.
- Celery Beat replaced by an Azure-native KEDA cron trigger so we have one less always-on container.
- Migration job runs pre-revision (deploy-time, not boot-time), so a bad migration never leaves the database in an inconsistent state for the running revision.

**Non-Goals:**

- Multi-region failover. Single region (`westeurope`). DR plan = restore Postgres backup + re-apply Bicep.
- Aggressive autoscaling. Defaults (min/max replicas) are pragmatic. Tuning is deferred until we have load data.
- Replacing `docker compose` for local development. Local dev stays as-is for the BE/worker/postgres/redis/frontend services; only Celery Beat goes away (replaced by a Make target invoking the cron script).
- Migrating to Azure SQL or Cosmos. Postgres remains the source of truth.
- Buying Azure DDoS Standard, WAF, Front Door, APIM. The Container Apps built-in ingress + managed certs are enough at our scale.
- AKS. Container Apps is the right level of abstraction for this app — no need for full Kubernetes.
- Real authentication for the admin panel beyond the existing JWT. SSO via Entra ID is a future change.

## Decisions

### Container Apps (Consumption profile) instead of App Service for Containers or AKS

- App Service for Containers is older, has a single-container-per-plan limitation, and doesn't natively support our multi-component shape (backend + worker + cron job).
- AKS is overkill — we'd be managing a Kubernetes control plane, RBAC, ingress controllers, etc. for an app with three containers.
- Container Apps Consumption profile gives us:
  - Scale-to-zero on the worker (€0 when idle).
  - HTTP ingress with managed TLS and custom domains baked in.
  - Revisions (blue/green) and traffic splitting natively.
  - KEDA scaling rules (HTTP concurrency for backend, Redis list length for worker, cron for the daily job).
  - Container App **Jobs** for one-shot work (migrations, seed admin) as a first-class concept.
- Tradeoff: cold starts on scale-to-zero (5-15s) — acceptable because the only thing scaling to zero is the worker, and the daily sync isn't latency-sensitive. The backend has `min_replicas=1` on prod.

### Replace Celery Beat with a KEDA-triggered Container App Job

- The existing `celery_beat` container is a long-running process whose only job is to fire one task at 03:00 UTC daily. Keeping it running 24/7 in Container Apps costs ~€8/month for nothing.
- KEDA's `cron` scaler can trigger a Container App Job on a schedule. The job runs `python -m app.scripts.cron_run_daily_sync`, which is a thin wrapper around `asyncio.run(run_daily_sync())`.
- Net result: one fewer container in production, one fewer service in the compose file, and the existing `run_daily_sync()` orchestrator works unchanged.
- We DELETE the `celery_beat` service from `docker-compose.yml`. Local dev gets a `make daily-sync` shortcut for the same script.
- Alternative considered: Azure Scheduler + HTTP webhook into an admin endpoint. Rejected because (a) it adds a second service to manage, (b) the endpoint becomes a security surface (must guard it), (c) KEDA cron is purpose-built for this and free.

### Image registry: GitHub Container Registry, not Azure Container Registry

- ACR Basic costs €4-5/month, GHCR is free for public + free for private under our seat count.
- Container Apps can pull from GHCR with a personal access token stored as a registry credential in the Container App config.
- We use the OIDC-federated GitHub Actions identity to push images (no PAT needed for the push step itself, GitHub provides `GITHUB_TOKEN`).
- For the pull, we provision one PAT scoped to `read:packages` and store it in Key Vault.
- Tradeoff: one extra secret to manage vs. €60/year saved. Worth it.

### OIDC federation, not service principal credentials

- The default GitHub-Azure pattern is to create a service principal, copy its `client_secret` into a GitHub Secret, rotate it manually. This is the wrong pattern — secrets in CI are a liability.
- The right pattern is **Workload Identity Federation**: configure the Azure App Registration to trust GitHub's OIDC issuer for the specific repo + branch. GitHub Actions then exchanges its short-lived OIDC token for an Azure access token at runtime. **No long-lived secrets anywhere.**
- We need to set this up ONCE during the bootstrap session — it requires an admin in the browser to grant consent.
- Each subsequent deploy is auditable: GitHub logs the workflow run, Azure logs the access token issuance, both correlated by the OIDC `sub` claim (repo:tierraaudio/ada_asm:ref:refs/heads/main).

### Migrations run as a Container App Job, pre-revision

- Today migrations run inside a `migrate` compose service that does `alembic upgrade head` once at boot. The new image only starts if the old image's container exits cleanly. This is fine locally but bad in cloud because:
  - If the migration is slow, the backend container starts before the schema is ready.
  - If the migration fails, the bad image is still running.
  - There's no way to roll back the migration without manually reverting the image.
- The cloud pattern: a separate Container App Job (`caj-ada-asm-migrate`) that the GitHub workflow invokes BEFORE updating the backend revision. Workflow steps:
  1. Build + push image to GHCR.
  2. Invoke `az containerapp job start --name caj-ada-asm-migrate --image <new-image>`.
  3. Wait for the job to exit cleanly (`az containerapp job execution show`).
  4. ONLY if migration succeeds: update the backend revision to the new image with `--revision-suffix=<sha>` and traffic split 100%.
  5. On failure: backend stays on the previous revision, migration failure is reported in the workflow run.
- This means a bad migration never takes the running backend down with it.

### Observability via OpenTelemetry + Azure Monitor (not Sentry, not BetterStack)

- We considered Sentry (best-in-class for errors, ~€26/month) and BetterStack (errors + logs, ~€24/month). Both are excellent and cross-cloud.
- We chose Application Insights because:
  - It's included in the Azure consumption (no extra subscription to manage), and 5 GB/month is free.
  - OpenTelemetry is the native instrumentation path — vendor-neutral, so we can swap exporters later without changing instrumentation code if we ever want to leave Azure.
  - Cross-tier correlation (FE page-view → BE request → SQL query) is the killer feature for debugging the lookup endpoint's 4-supplier fan-out.
  - The Bicep template provisions a pre-built dashboard tracking the specific metrics we care about (supplier-sync success rate, p95 lookup latency, Redis cache hit ratio).
- The `observability.py` module is a no-op when `APPLICATIONINSIGHTS_CONNECTION_STRING` is absent, so local dev gets zero impact and zero risk of leaking traces to a wrong tenant.
- Sampling: we keep 100% of HTTP traces and 10% of SQL spans in prod. App Insights' 5 GB/month free tier is enough at our current request volume; we'll revisit if we cross.

### Two custom domains, not one

- Pattern A (chosen): `ada.tierra.audio` (FE) + `api.ada.tierra.audio` (BE). Each is a separate Azure resource with its own managed cert.
- Pattern B (rejected): `ada.tierra.audio` for both with path-based routing — would require Azure Front Door (€35/month) or a custom reverse proxy.
- A wins on cost (€0 extra) and on clarity: CORS is a clean allowlist of one origin, cookies have a clear domain scope, the FE knows exactly where the API lives via build-time `VITE_API_URL`.

### Bicep, not Terraform

- Terraform is more widely portable, but for an all-Azure single-cloud target, Bicep is:
  - First-party: deployed via `az deployment group create`, no extra binary.
  - Strongly typed against the Azure resource provider API (better autocompletion, IDE warnings).
  - The native ARM template language compiled down — guaranteed to track Azure resource updates without a provider lag.
- Tradeoff: less portable if we ever leave Azure. But the decision is all-Azure with no exit plan, so portability is hypothetical.

### Postgres Flexible Server (Burstable B1ms dev / B2s prod)

- Single Server is being deprecated by Azure. Flexible Server is the path forward.
- B1ms (1 vCPU / 2 GB) for dev: ~€13/month. Burstable means it can spike to 1 full vCPU for short bursts, which is plenty for a single developer's tests.
- B2s (2 vCPU / 4 GB) for prod: ~€26/month. Same Burstable family, just more headroom.
- Geo-redundant backups on prod (€2/month extra), locally-redundant on dev.
- HA disabled on both — we don't need 99.99% uptime at our scale. Restoring from a 5-min-old backup is acceptable DR.
- Extensions: `pgcrypto` (for `gen_random_uuid()`), `ltree` (we use it on `Module.path`), `pg_stat_statements` (free, useful for debugging slow queries). All enabled at server creation via the `azure.extensions` parameter.

### Redis: Basic C0 dev + prod (downgrade from spec's Standard C1)

- The enriched draft proposed Standard C1 for prod (€40/month, 99.9% SLA). On reflection, we have:
  - No SLA target documented anywhere.
  - The only thing in Redis is the Celery broker + rate-limit token buckets + FX cache + lookup cache. None of those are unrecoverable on data loss.
  - The Celery worker's `acks_late=True` config means in-flight tasks survive a Redis blip.
- Basic C0 (€16/month, 250 MB, no SLA) is enough until we have evidence we need more.
- Both dev and prod use Basic C0. We can upgrade to Standard later without a Bicep template rewrite — just change the SKU param.

## Risks / Trade-offs

- **OIDC federation setup requires an admin in the browser** — the bootstrap is not fully automated. Mitigation: documented in the runbook; one-time cost.
- **Azure Static Web Apps free tier has bandwidth limits** (100 GB/month outbound). At our current size we won't approach it, but if the dashboard becomes popular it might. Mitigation: upgrade to Standard (€10/month) if we cross 80%.
- **Postgres Flexible Server Burstable tier means burstable CPU** — sustained high load (a busy daily sync) might throttle. Mitigation: the daily sync runs at 03:00 UTC when nothing else hits the DB; if it becomes slow, upgrade to a non-burstable SKU.
- **KEDA cron jobs can occasionally miss a fire** if the underlying KEDA controller is unhealthy. Mitigation: the run script is idempotent (existing INSERT … ON CONFLICT logic), so a manual re-run if we notice a missed day is safe.
- **App Insights 5 GB free tier might be exceeded** if SQL span sampling is too aggressive or if the traffic grows. Mitigation: we start at 10% SQL sampling; upgrade trigger is hitting €5/month in App Insights data ingestion charges.
- **Container Apps cold starts on scale-to-zero** — the worker takes 5-15s to start when a task lands after idle. Mitigation: the only thing scaling to zero is the worker (the backend has `min_replicas=1` on prod); the daily sync isn't latency-sensitive. The lookup endpoint stays warm via backend's min replica.
- **GHCR rate limits** — GitHub limits container pulls to 5000/hour for anonymous, 60/hour for authenticated free accounts. Container Apps with a PAT credential should be fine, but if we hit it, upgrading to a paid GHCR plan is €5/month.
- **DNS propagation during cutover** — Azure DNS TTL defaults to 3600s (1 hour). The legacy `134.0.10.173` A record needs to be deleted, the new CNAMEs added, and a managed cert provisioned. Worst case: ~1 hour of `ada.tierra.audio` serving the legacy redirect to cached resolvers. Mitigation: lower the TTL to 300s 24h before cutover, do the cutover at low-traffic UTC, monitor with `dig` from multiple resolvers.

## Migration Plan

1. **Bootstrap session (user + Claude, ~30 min)**:
   - Device-code `az login` as Azure tenant admin.
   - Provision a dedicated GitHub App Registration with Federated Identity Credential for `tierraaudio/ada_asm:ref:refs/heads/main`.
   - Grant the App Registration `Contributor` on the (to-be-created) Resource Group.
   - Admin grants consent for any required Microsoft Graph scopes (one click).
2. **Provision `dev` first** via `az deployment group create --template-file infra/azure/main.bicep --parameters environment=dev`. Validate everything works in `dev` before touching `prod`.
3. **Manually load secrets into `dev` Key Vault** (user, ~10 min) — JWT secret, supplier API keys. The Bicep stubs the secrets as empty so the deploy doesn't fail, then the user fills the real values.
4. **Push `main`** — GitHub Actions runs the backend + frontend deploy workflows against `dev`. Verify health, run the seed admin job, sign in.
5. **Smoke test `dev`**: lookup endpoint, ad-hoc supplier sync, App Insights showing traces.
6. **Provision `prod`** — same Bicep template, `environment=prod`. Cost target verification.
7. **DNS cutover for prod** (user present, ~10 min): delete legacy A record → wait for TTL → verify CNAMEs propagated → trigger managed cert issuance → verify `https://ada.tierra.audio` and `https://api.ada.tierra.audio/api/v1/health` are 200.
8. **Operational handoff**: dashboard URL, alert recipient, key vault rotation runbook.

**Rollback:**

- If the Bicep deploy fails mid-way: `az deployment group create --what-if` always runs first; failed deploys leave the previous state intact (Bicep is idempotent).
- If the backend revision fails health probes after a new deploy: traffic stays on the previous revision (Container Apps' default behaviour). Manual rollback: `az containerapp revision set-mode --mode single --revision <previous>`.
- If a migration fails: the backend revision is never promoted (gated by the migration job). The previous backend revision is still serving.
- If the DNS cutover goes wrong: the legacy A record can be re-added in <1 min in Azure DNS. Worst case the SPA is down for the TTL window (300s if we lowered it pre-cutover).

## Open Questions

- **Should we provision `dev` and `prod` in the SAME subscription or two?** A single subscription with two RGs is simpler operationally; two subscriptions give clean cost boundaries for finance reporting. Default: single subscription, two RGs.
- **GitHub Actions OIDC subject claim filter** — do we restrict to `ref:refs/heads/main` only or also allow `ref:refs/heads/staging` if we ever add a staging branch? Default: `main` only; expand later.
- **App Insights sampling** — 10% SQL spans is a guess. Start there, revisit when we have a month of data.
- **Container App health probe URL** — `/api/v1/health` exists and returns 200 with no auth. Is that the right probe target or do we need a deeper probe that touches Postgres? Default: `/api/v1/health` for liveness; a deeper `/api/v1/ready` (Postgres + Redis check) for readiness is a follow-up.
- **Static Web App's free tier vs. Standard** — start free, upgrade only when bandwidth bites.
