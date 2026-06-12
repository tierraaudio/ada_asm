## MODIFIED Requirements

### Requirement: Every sensitive value lives in Key Vault, not in source

The system SHALL persist every sensitive value (API keys, JWT secret, supplier credentials, App Insights connection string, admin bootstrap credentials, database/celery connection URLs) ONLY in the per-environment Azure Key Vault. The Bicep `keyvault.bicep` module SHALL pre-create the named secret list at apply time without values; the runbook documents loading the values via `az keyvault secret set`.

The expected secret name list is:

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

`ghcr-pull-token` is NO LONGER part of this list — container registry pulls authenticate via system-assigned managed identity on ACR.

#### Scenario: No secrets appear in the Bicep templates

- **WHEN** an operator runs `grep -r "ghp_\|api[-_]key\|client[-_]secret\|password" infra/azure/`
- **THEN** no literal secret values are returned (only `@secure()` parameter declarations and Key Vault secret references)

#### Scenario: No secrets appear in container env literals

- **WHEN** an operator runs `az containerapp show --name ca-ada-asm-<env>-backend` and inspects the `template.containers[0].env` array
- **THEN** every sensitive env var has `secretRef:` pointing at a Container App secret
- **AND** every Container App secret has `keyVaultUrl:` pointing at the Key Vault, NOT an inline `value:`

#### Scenario: No registry pull credential is stored in Key Vault

- **WHEN** the operator runs `az keyvault secret list --vault-name kv-ada-asm-<env>`
- **THEN** the list does NOT contain `ghcr-pull-token` (or any other registry pull token)
- **AND** Container Apps' `properties.configuration.registries` for the backend, worker, and all 3 Jobs uses `identity: 'system'`, not `passwordSecretRef`

## REMOVED Requirements

### Requirement: GHCR pull credential is rotated through Key Vault

**Reason**: Container Apps now pull from ACR via the system-assigned managed identity. There is no PAT to rotate.

**Migration**: Grant `AcrPull` on the per-environment ACR scope to each Container App + Job system MI (see `cloud-infrastructure` spec). Delete the existing `ghcr-pull-token` secret from `kv-ada-asm-dev` once the new path is proven green.
