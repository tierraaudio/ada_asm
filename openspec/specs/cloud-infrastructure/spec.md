# cloud-infrastructure Specification

## Purpose
Bicep-defined Azure stack (Container Apps Environment, Container Apps + Jobs, ACR, Postgres Flexible Server, Static Web App, self-hosted Redis cache, Storage Queues broker) provisioned from `infra/azure/main.bicep`.

## Requirements

### Requirement: The full Azure stack is provisioned from Bicep

The system SHALL host all Infrastructure-as-Code under `infra/azure/` with `main.bicep` as the entry point and per-resource modules under `infra/azure/modules/`. A single `az deployment group create --template-file infra/azure/main.bicep --parameters environment=<env>` invocation SHALL provision the entire stack from scratch for either `dev` or `prod`.

#### Scenario: Fresh `dev` provisioning succeeds end-to-end

- **WHEN** an operator runs `az deployment group create --template-file infra/azure/main.bicep --parameters environment=dev` against an empty resource group
- **THEN** the deployment completes successfully
- **AND** the following resources exist in the resource group:
  - 1 Log Analytics Workspace + 1 Application Insights instance
  - 1 Container Apps Environment
  - 2 Container Apps (`ca-ada-asm-backend-dev`, `ca-ada-asm-worker-dev`)
  - 3 Container App Jobs (`caj-ada-asm-migrate-dev`, `caj-ada-asm-seed-admin-dev`, `caj-ada-asm-beat-cron-dev`)
  - 1 Postgres Flexible Server with `pgcrypto`, `ltree`, `pg_stat_statements` enabled
  - 1 Azure Cache for Redis (Basic C0, TLS-only)
  - 1 Static Web App
  - 1 Key Vault (RBAC mode, soft-delete + purge protection on)
  - DNS records `ada` + `api.ada` as CNAMEs to the SWA + ACA endpoints
- **AND** `az deployment group what-if` immediately after returns "no changes" (idempotency confirmed)

### Requirement: `dev` and `prod` are parameterised, not duplicated

The system SHALL accept an `environment` parameter (`dev` | `prod`) that drives SKU sizing and naming. Both environments use the same Bicep templates with different parameter files (`infra/azure/parameters.dev.bicepparam`, `infra/azure/parameters.prod.bicepparam`).

#### Scenario: Dev and prod use different Postgres SKUs

- **WHEN** the operator deploys with `environment=dev`
- **THEN** the Postgres Flexible Server is provisioned with SKU `Standard_B1ms` (1 vCPU / 2 GB RAM)

- **WHEN** the operator deploys with `environment=prod`
- **THEN** the Postgres Flexible Server is provisioned with SKU `Standard_B2s` (2 vCPU / 4 GB RAM)

#### Scenario: Naming convention uses the environment suffix

- **WHEN** any resource is provisioned
- **THEN** its name follows the pattern `<short-resource-type>-ada-asm-<environment>` (e.g. `ca-ada-asm-backend-dev`, `pg-ada-asm-prod`)

### Requirement: Container App `backend` exposes the API on a custom domain with managed TLS

The system SHALL configure the `ca-ada-asm-backend-<env>` Container App with public HTTP ingress on port 8000, custom domain `api.ada.tierra.audio` (prod) or `api.ada-dev.tierra.audio` (dev), and an Azure-managed TLS certificate that auto-renews.

#### Scenario: Backend custom domain serves HTTPS with a valid cert

- **WHEN** an unauthenticated client opens `https://api.ada.tierra.audio/api/v1/health`
- **THEN** the response is HTTP 200 with JSON `{"status": "ok", ...}`
- **AND** the TLS certificate is issued by DigiCert (or Azure's chosen managed cert authority)
- **AND** the certificate's `Subject Alternative Name` includes `api.ada.tierra.audio`

### Requirement: Static Web App serves the SPA on `ada.tierra.audio`

The system SHALL provision an Azure Static Web App with custom domain `ada.tierra.audio` (prod) / `ada-dev.tierra.audio` (dev), connected via OIDC to the GitHub repository, and configured with the `staticwebapp.config.json` at the repo root.

#### Scenario: SPA loads at the custom domain

- **WHEN** a browser navigates to `https://ada.tierra.audio/`
- **THEN** the response is HTTP 200 with the SPA's `index.html`
- **AND** the `Content-Security-Policy` response header is set
- **AND** the `Strict-Transport-Security` response header is set with `max-age >= 31536000`

#### Scenario: Unknown SPA route falls back to index.html

- **WHEN** the browser navigates to `https://ada.tierra.audio/components/new`
- **AND** there is no static asset at that path
- **THEN** the response is HTTP 200 with the SPA's `index.html` (so React Router can resolve client-side)

### Requirement: Postgres is provisioned with the extensions the app requires

The system SHALL provision the Postgres Flexible Server with `pgcrypto`, `ltree`, and `pg_stat_statements` extensions enabled at server creation via the `azure.extensions` parameter, AND SHALL configure SSL-required connections (`require_secure_transport=on`).

#### Scenario: Connections without SSL are rejected

- **WHEN** a client attempts to connect to the Postgres server without TLS
- **THEN** the connection is refused

#### Scenario: `pgcrypto` is available for the existing migrations

- **WHEN** the migration `20260523_1800_component_management__components_and_purchases.py` runs against the provisioned server
- **THEN** the `gen_random_uuid()` function resolves and the migration completes successfully

### Requirement: Redis is provisioned in TLS-only mode

The system SHALL provision the Azure Cache for Redis instance with the non-TLS port disabled (`enableNonSslPort: false`). All clients connect via `rediss://`.

#### Scenario: Non-TLS connections are refused

- **WHEN** a Celery worker attempts to connect to `redis://...` on port 6379
- **THEN** the connection is refused

#### Scenario: TLS connections succeed

- **WHEN** the Celery worker connects via `rediss://...:6380` with the access key
- **THEN** the connection is established and the worker starts polling tasks

### Requirement: DNS records are provisioned through Bicep

The system SHALL provision the following records in the Azure DNS zone `tierra.audio`:

- `ada` (CNAME → the Static Web App's default hostname)
- `api.ada` (CNAME → the backend Container App's default hostname)
- `asuid.ada` (TXT for SWA custom-domain ownership validation)
- `asuid.api.ada` (TXT for ACA custom-domain ownership validation)

The pre-existing `ada.tierra.audio → 134.0.10.173` A record (legacy redirect to tierraaudio.com) SHALL be deleted as part of the cutover, documented in `infra/azure/RUNBOOK_DNS_CUTOVER.md`.

#### Scenario: DNS records resolve after deploy

- **WHEN** the Bicep deploy completes
- **AND** the operator runs `dig ada.tierra.audio CNAME` and `dig api.ada.tierra.audio CNAME`
- **THEN** both return the expected Azure-managed hostnames

#### Scenario: Legacy A record is gone

- **WHEN** the DNS cutover runbook has been executed
- **THEN** `dig ada.tierra.audio +short` does NOT return `134.0.10.173`

### Requirement: A monitoring dashboard ships with the deploy

The system SHALL deploy a pre-built Application Insights dashboard via `infra/azure/dashboard.json`. The dashboard SHALL contain at minimum:

- Backend HTTP p50 / p95 / p99 latency tiles
- Backend HTTP 5xx rate tile
- Supplier sync success rate per day tile
- Redis cache hit ratio on `/components/lookup` tile
- Frontend page-view count + bounce-rate tile

#### Scenario: The dashboard is available in the Azure Portal after deploy

- **WHEN** the deploy completes
- **AND** the operator navigates to "Shared Dashboards" in the Azure Portal
- **THEN** the `dashboard-ada-asm-<env>` dashboard is listed and visible

### Requirement: A 5xx alert routes to the operations email

The system SHALL provision one Application Insights alert rule: backend HTTP 5xx rate > 5% over 5 minutes → email `ops@tierra.audio`. The alert rule SHALL be defined in `infra/azure/modules/alerts.bicep`.

#### Scenario: A simulated 5xx burst triggers the alert

- **WHEN** the backend returns HTTP 500 on more than 5% of requests over 5 minutes
- **THEN** an email is delivered to `ops@tierra.audio` within the next alert evaluation window

### Requirement: Key Vault seeds the secrets list at deploy time

The system SHALL seed the per-environment Key Vault with the following secret names at Bicep apply time:

- `jwt-secret`
- `mouser-api-key`
- `digikey-client-id`, `digikey-client-secret`
- `tme-token`, `tme-app-secret`
- `farnell-api-key`
- `rs-api-key`
- `app-insights-connection-string`
- `seed-admin-email`, `seed-admin-password`
- `database-url`
- `celery-broker-url`

The `ghcr-pull-token` secret SHALL NOT be seeded — the GHCR-based pull path is decommissioned in favor of ACR + system MI.

#### Scenario: Backend reads JWT secret from Key Vault at runtime

- **WHEN** the backend Container App starts
- **THEN** the `JWT_SECRET` env var is populated from `secretref:jwt-secret`
- **AND** the value matches what is stored in the Key Vault at `jwt-secret`

#### Scenario: Rotating a secret does not require a code redeploy

- **WHEN** the operator updates `kv-ada-asm-<env>` secret `mouser-api-key` to a new value
- **THEN** the next Container App revision picks up the new value via its KV reference
- **AND** no Bicep re-apply or workflow run is required

#### Scenario: No ghcr-pull-token in Key Vault

- **WHEN** an operator runs `az keyvault secret list --vault-name kv-ada-asm-<env>`
- **THEN** no secret named `ghcr-pull-token` is returned

### Requirement: Each environment provisions a dedicated Azure Container Registry

The system SHALL provision one Azure Container Registry per environment in the same resource group as Container Apps. The ACR SHALL be Basic SKU, located in the same region as Container Apps (no cross-region pull egress), with the admin user disabled. The ACR name SHALL follow the pattern `acradaasm<env>` (alphanumeric only; ACR name constraints). The ACR is created by a dedicated Bicep module `infra/azure/modules/acr.bicep` and is wired in `main.bicep` BEFORE the `containerApps` and `containerJobs` modules.

#### Scenario: Dev environment has a dedicated ACR

- **WHEN** an operator inspects `rg-ada-asm-dev`
- **THEN** an ACR resource named `acradaasmdev` exists
- **AND** the SKU is `Basic`
- **AND** `adminUserEnabled` is `false`
- **AND** the location matches the Container Apps Environment location

### Requirement: System-assigned managed identities hold AcrPull on the per-environment ACR

The system SHALL grant the built-in `AcrPull` role on the per-environment ACR scope to the system-assigned managed identity of every Container App AND every Container App Job in that environment. Role assignment names SHALL be deterministic GUIDs derived from `(acrId, principalId, roleDefinitionId)` so Bicep re-applies are idempotent.

#### Scenario: Backend Container App can pull from ACR via MI

- **WHEN** the backend Container App's system MI principal ID is listed against the per-environment ACR scope
- **THEN** at least one role assignment exists for that principal with role `AcrPull`
- **AND** the role assignment scope is the ACR resource ID (not the resource group)

#### Scenario: All 3 Jobs can pull from ACR via MI

- **WHEN** an operator runs `az role assignment list --scope <acrId> --role AcrPull`
- **THEN** the list includes the principal IDs of `caj-ada-asm-<env>-migrate`, `caj-ada-asm-<env>-seed-admin`, and `caj-ada-asm-<env>-beat-cron`

### Requirement: The deploy UAMI holds AcrPush on the per-environment ACR

The system SHALL grant the built-in `AcrPush` role on the per-environment ACR scope to the deploy UAMI (`id-deploy-ada-asm-<env>`). This is the same UAMI that GitHub Actions assumes via OIDC federation. No other identity SHALL have push rights on the ACR.

#### Scenario: GitHub Actions can push to ACR via OIDC

- **WHEN** the `deploy-backend.yml` workflow runs `az acr login --name acradaasm<env>` after `azure/login@v2`
- **THEN** the login succeeds using the federated UAMI token
- **AND** a subsequent `docker push` to `acradaasm<env>.azurecr.io/ada-asm-backend:<tag>` returns 201

