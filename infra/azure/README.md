# `infra/azure/` — Infrastructure-as-Code for the Azure deployment

This directory holds the [Bicep](https://learn.microsoft.com/azure/azure-resource-manager/bicep/) templates that provision the entire ada_asm stack on Azure. The change `cloud-deployment-azure` introduced this directory; the proposal / design / specs for what gets provisioned live under [`openspec/changes/`](../../openspec/changes/) (active) or [`openspec/changes/archive/`](../../openspec/changes/archive/) (after archive).

## Layout

```
infra/azure/
├── main.bicep                  # entry point — orchestrates the modules
├── parameters.dev.bicepparam   # dev parameter file (cheap SKUs, scale-to-zero)
├── parameters.prod.bicepparam  # prod parameter file (slightly larger SKUs, geo backups)
├── modules/                    # one Bicep module per logical layer
│   ├── foundation.bicep        # Log Analytics + Application Insights
│   ├── network.bicep           # Container Apps Environment
│   ├── data.bicep              # Postgres Flexible Server
│   ├── redis.bicep             # Azure Cache for Redis
│   ├── keyvault.bicep          # Key Vault (RBAC mode)
│   ├── identity.bicep          # GitHub Federated Identity Credential
│   ├── container_apps.bicep    # 2 Container Apps (backend, worker)
│   ├── container_jobs.bicep    # 3 Container App Jobs (migrate, seed-admin, beat-cron)
│   ├── static_web_app.bicep    # Static Web App for the SPA
│   ├── dns.bicep               # CNAMEs + TXT records
│   ├── dashboard.bicep         # Application Insights dashboard
│   └── alerts.bicep            # 5xx alert rule
├── dashboard.json              # serialized App Insights dashboard tiles
├── RUNBOOK_DNS_CUTOVER.md      # step-by-step cutover incl. legacy A-record cleanup
├── RUNBOOK_SECRET_ROTATION.md  # per-secret rotation procedures
└── RUNBOOK_INCIDENT_RESPONSE.md # what to do when the 5xx alert fires
```

Modules are added incrementally by the `cloud-deployment-azure` change's tasks (1.2 - 1.13). `main.bicep` keeps the wiring section commented-out until each module lands so the template compiles clean at every checkpoint.

## Prerequisites

- `az` CLI 2.60+ with the `az bicep` extension installed (`az bicep upgrade`).
- A logged-in `az` session targeting the tierraaudio Azure tenant.
- A pre-created resource group: `rg-ada-asm-dev` or `rg-ada-asm-prod`.

## Quick commands

```bash
# Compile the templates (catches syntax errors, validates against the Azure resource provider schema):
az bicep build --file infra/azure/main.bicep

# Preview what would change in dev WITHOUT applying:
az deployment group what-if \
  --resource-group rg-ada-asm-dev \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.dev.bicepparam

# Apply to dev:
az deployment group create \
  --resource-group rg-ada-asm-dev \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.dev.bicepparam

# Apply to prod (always run what-if first, manually review the output):
az deployment group create \
  --resource-group rg-ada-asm-prod \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.prod.bicepparam
```

## Cost expectations

| Environment | Idle floor | Active estimate |
| ----------- | ---------- | --------------- |
| dev         | ~€33/month (Postgres B1ms + Redis Basic C0; everything else scales to zero) | ~€35/month |
| prod        | ~€40/month (Postgres B2s + Redis Basic C0 + ~€2 storage + alerts) | ~€45/month at our current traffic |

The biggest single cost is Postgres Flexible Server. If a future change adds proper SLAs, the SKU upgrade is a one-line parameter change.

## Naming convention

Every resource follows `<short-resource-type>-<projectSlug>-<environment>`:

| Resource | Pattern | Example |
| -------- | ------- | ------- |
| Resource Group | `rg-<slug>-<env>` | `rg-ada-asm-prod` |
| Log Analytics | `log-<slug>-<env>` | `log-ada-asm-prod` |
| Application Insights | `appi-<slug>-<env>` | `appi-ada-asm-prod` |
| Container Apps Env | `cae-<slug>-<env>` | `cae-ada-asm-prod` |
| Container App (backend) | `ca-<slug>-backend-<env>` | `ca-ada-asm-backend-prod` |
| Container App (worker) | `ca-<slug>-worker-<env>` | `ca-ada-asm-worker-prod` |
| Container App Job | `caj-<slug>-<purpose>-<env>` | `caj-ada-asm-migrate-prod` |
| Postgres Flexible Server | `pg-<slug>-<env>` | `pg-ada-asm-prod` |
| Cache for Redis | `redis-<slug>-<env>` | `redis-ada-asm-prod` |
| Static Web App | `stapp-<slug>-<env>` | `stapp-ada-asm-prod` |
| Key Vault | `kv-<slug>-<env>` | `kv-ada-asm-prod` |

## Runbooks

- **DNS cutover** ([RUNBOOK_DNS_CUTOVER.md](RUNBOOK_DNS_CUTOVER.md)): one-time event when prod first goes live, including the deletion of the pre-existing legacy `ada.tierra.audio → 134.0.10.173` A record.
- **Secret rotation** ([RUNBOOK_SECRET_ROTATION.md](RUNBOOK_SECRET_ROTATION.md)): per-secret rotation procedures.
- **Incident response** ([RUNBOOK_INCIDENT_RESPONSE.md](RUNBOOK_INCIDENT_RESPONSE.md)): what to do when the 5xx alert fires.

## Related documentation

- Top-level deployment guide: [`ai-specs/specs/development_guide.md`](../../ai-specs/specs/development_guide.md) §11.
- Backend cloud configuration conventions: [`ai-specs/specs/backend-standards.mdc`](../../ai-specs/specs/backend-standards.mdc).
- Change history: [`openspec/changes/archive/`](../../openspec/changes/archive/).
