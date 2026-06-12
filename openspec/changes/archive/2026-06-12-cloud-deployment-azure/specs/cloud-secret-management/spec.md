## ADDED Requirements

### Requirement: Every production secret lives in Key Vault, not in code or env files

The system SHALL store the following secrets in `kv-ada-asm-<env>` and NOWHERE else in the deployed system:

- `jwt-secret`
- `postgres-admin-password`
- `redis-primary-key`
- `mouser-api-key`
- `digikey-client-id`, `digikey-client-secret`
- `tme-token`, `tme-app-secret`
- `farnell-api-key`
- `rs-api-key`
- `app-insights-connection-string`
- `seed-admin-email`, `seed-admin-password`
- `ghcr-pull-token`

#### Scenario: No secrets appear in the Bicep templates

- **WHEN** an operator runs `grep -r "ghp_\|ghp_\|api[-_]key\|client[-_]secret\|password" infra/azure/`
- **THEN** no literal secret values are returned (only `@secure()` parameter declarations and Key Vault secret references)

#### Scenario: No secrets appear in container env literals

- **WHEN** an operator runs `az containerapp show --name ca-ada-asm-backend-<env>` and inspects the `template.containers[0].env` array
- **THEN** every sensitive env var has `secretRef:` pointing at a Container App secret
- **AND** every Container App secret has `keyVaultUrl:` pointing at the Key Vault, NOT an inline `value:`

### Requirement: Container Apps authenticate to Key Vault via system-assigned managed identity

The system SHALL configure each Container App and Container App Job with a system-assigned managed identity, and SHALL grant that identity the `Key Vault Secrets User` role on `kv-ada-asm-<env>`. RBAC role assignments live in Bicep — no manual portal clicks.

#### Scenario: A new revision can read secrets without re-granting RBAC

- **WHEN** the GitHub Actions workflow promotes a new backend revision
- **THEN** the new revision picks up the same system-assigned identity
- **AND** the identity continues to have `Key Vault Secrets User` on the vault
- **AND** secret resolution succeeds without manual intervention

### Requirement: Key Vault has soft-delete and purge protection enabled

The system SHALL provision the Key Vault with `enableSoftDelete=true` (retention 90 days) and `enablePurgeProtection=true`. These cannot be disabled after the fact, which is the point.

#### Scenario: A deleted secret is recoverable for 90 days

- **WHEN** an operator deletes the `jwt-secret` secret
- **THEN** the secret enters the soft-deleted state
- **AND** `az keyvault secret recover --name jwt-secret` restores it for 90 days after deletion

### Requirement: Rotating a secret does not require a code redeploy

The system SHALL configure Container Apps to resolve `secretRef:` values from Key Vault at revision-start time. Rotating a secret in Key Vault and restarting the Container App revision SHALL pick up the new value with no image rebuild and no code change.

#### Scenario: Rotating mouser-api-key applies on restart

- **WHEN** the operator updates `kv-ada-asm-prod` secret `mouser-api-key` to a new value
- **AND** runs `az containerapp revision restart --name ca-ada-asm-backend-prod --revision <current>`
- **THEN** the next call to the Mouser adapter uses the new API key
- **AND** no image was rebuilt
- **AND** no commit was pushed

### Requirement: A documented rotation runbook covers every secret

The system SHALL include `infra/azure/RUNBOOK_SECRET_ROTATION.md` with per-secret rotation procedures: where to obtain the new value (supplier portal, Azure-generated, etc.), the `az keyvault secret set` command to apply it, and the Container App restart command. The runbook SHALL also document the response if a secret leaks (rotate immediately, audit access logs via Log Analytics).

#### Scenario: The runbook covers every Key Vault secret

- **WHEN** an operator opens `infra/azure/RUNBOOK_SECRET_ROTATION.md`
- **THEN** every secret listed in this capability's first requirement has its own subsection with rotation steps
