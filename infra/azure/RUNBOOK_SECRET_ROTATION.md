# Secret rotation runbook

Every production secret lives in `kv-ada-asm-<env>`. This runbook documents the rotation procedure per secret.

## Generic rotation pattern

1. Update the secret in Key Vault:
   ```bash
   az keyvault secret set --vault-name kv-ada-asm-prod --name <secret-name> --value '<new-value>'
   ```
2. Restart the Container App revision so it picks up the new value:
   ```bash
   az containerapp revision restart --resource-group rg-ada-asm-prod --name ca-ada-asm-prod-backend --revision $(az containerapp revision list --resource-group rg-ada-asm-prod --name ca-ada-asm-prod-backend --query "[?properties.active].name | [0]" -o tsv)
   az containerapp revision restart --resource-group rg-ada-asm-prod --name ca-ada-asm-prod-worker --revision $(az containerapp revision list --resource-group rg-ada-asm-prod --name ca-ada-asm-prod-worker --query "[?properties.active].name | [0]" -o tsv)
   ```
3. Verify with a smoke test against the affected dependency (e.g. `POST /api/v1/supplier-sync/runs?supplier=mouser` after rotating `mouser-api-key`).

## Per-secret procedures

### `jwt-secret`

- **When**: every 90 days, or immediately on suspected compromise.
- **Source**: generated locally:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- **Apply**: generic pattern above.
- **Impact**: signed-in users keep working — refresh tokens are validated against the database allow-list, not the JWT signature. Their next refresh issues a new access token signed with the new secret. No user-visible downtime.

### `postgres-admin-password`

- **When**: every 90 days, or immediately on suspected compromise.
- **Source**:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Apply**:
  1. Update in Postgres: `ALTER ROLE adaasm_admin WITH PASSWORD '<new>';` (requires logging in via `az postgres flexible-server connect` once with the OLD password).
  2. Update in Key Vault.
  3. Restart backend + worker.
- **Impact**: brief connection-pool flush during the restart.

### `redis-primary-key`

- **When**: on suspected compromise. Otherwise, the Azure-managed key rotates automatically every 365 days.
- **Source**: Azure-generated.
- **Apply**:
  ```bash
  az redis regenerate-keys --resource-group rg-ada-asm-prod --name redis-ada-asm-prod --key-type Primary
  NEW_KEY=$(az redis list-keys --resource-group rg-ada-asm-prod --name redis-ada-asm-prod --query primaryKey -o tsv)
  az keyvault secret set --vault-name kv-ada-asm-prod --name redis-primary-key --value "$NEW_KEY"
  # Restart backend + worker.
  ```
- **Impact**: ~5-15s of dropped Redis connections during the regenerate. Celery acks_late + retries handle in-flight tasks.

### Supplier API keys (`mouser-api-key`, `digikey-client-secret`, `tme-app-secret`, `farnell-api-key`, `rs-api-key`)

- **When**: when the supplier rotates them (rare), or on suspected leak.
- **Source**: each supplier's developer portal:
  - Mouser: [mouser.com/api-hub/](https://www.mouser.com/api-hub/) → "Regenerate"
  - DigiKey: [developer.digikey.com](https://developer.digikey.com) → app page → "Regenerate Client Secret"
  - TME: [developers.tme.eu](https://developers.tme.eu) → app page → "Generate new private key" (requires the 600s temporary token from www.tme.eu)
  - Farnell: [partner.element14.com](https://partner.element14.com) → app page → "Regenerate Key"
  - RS: email RS commercial rep for a new App ID
- **Apply**: generic pattern. Smoke test the affected supplier via `POST /api/v1/supplier-sync/runs?supplier=<code>`.

### `ghcr-pull-token`

- **When**: every 12 months (GitHub PAT max lifetime).
- **Source**: GitHub UI → `tierraaudio-bot` service account → `Settings → Developer settings → Personal access tokens → Fine-grained tokens`. Scope: `read:packages` only. Expiry: 364 days.
- **Apply**: generic pattern. Container Apps re-authenticate on the next revision restart.

### `seed-admin-email` / `seed-admin-password`

- These are only consumed by the `caj-ada-asm-<env>-seed-admin` Container App Job and only on first deploy. Rotation is irrelevant after the first admin user exists.
- If the initial admin password leaks BEFORE the user signs in, rotate via the standard password-reset flow (the seed job is idempotent — re-running it on an existing admin is a no-op).

### `app-insights-connection-string`

- **When**: only if the Application Insights resource is destroyed and recreated.
- **Source**: `az monitor app-insights component show --resource-group rg-ada-asm-prod --app appi-ada-asm-prod --query connectionString -o tsv`.
- **Apply**: generic pattern + redeploy the frontend (the FE build inlines the connection string at build time, so it needs a fresh `deploy-frontend.yml` run).

## On suspected leak — incident response

If you believe ANY secret has leaked:

1. **Rotate immediately** following the per-secret procedure above.
2. **Audit access logs**:
   ```bash
   az monitor log-analytics query \
     --workspace $(az monitor log-analytics workspace show --resource-group rg-ada-asm-prod --workspace-name log-ada-asm-prod --query customerId -o tsv) \
     --analytics-query "AzureDiagnostics | where ResourceProvider == 'MICROSOFT.KEYVAULT' | where ResourceId contains 'kv-ada-asm-prod' | where TimeGenerated > ago(7d)"
   ```
3. **For supplier keys**: contact the supplier (suppliers often have their own audit logs and can tell you whether the key was used outside our egress IP).
4. **For JWT secret**: also revoke ALL active refresh tokens (truncate the `refresh_tokens` table). All users will be forced to sign in again.
5. **Log the incident** in `infra/azure/RUNBOOK_INCIDENT_RESPONSE.md`.
