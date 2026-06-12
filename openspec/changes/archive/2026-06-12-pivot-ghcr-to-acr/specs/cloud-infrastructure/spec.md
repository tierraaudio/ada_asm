## ADDED Requirements

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

## MODIFIED Requirements

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
