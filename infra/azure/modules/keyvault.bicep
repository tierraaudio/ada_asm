// Key Vault (RBAC mode).
//
// Per the spec:
// - RBAC, NOT access policies (the modern shape).
// - Soft-delete 90d + purge protection — irreversible by design.
// - Holds 14 named secrets (see the spec for the full list).
//
// The Bicep stubs each secret as a `Microsoft.KeyVault/vaults/secrets`
// child resource with an empty/placeholder value so the deploy doesn't
// fail on missing children. The OPERATOR loads the real values manually
// after the first deploy via `az keyvault secret set` — Claude provides
// the exact commands in RUNBOOK_SECRET_ROTATION.md but never sees the
// values.

param environment string
param location string
param nameSuffix string

@description('Tenant ID for RBAC role assignments. Defaults to the deployment tenant.')
param tenantId string = subscription().tenantId

// Logical list of secrets to provision. Each is created with a
// placeholder value the operator MUST overwrite before the dependent
// Container Apps revision can start cleanly.
var secretNames = [
  'jwt-secret'
  'postgres-admin-password'
  'redis-primary-key'
  'mouser-api-key'
  'digikey-client-id'
  'digikey-client-secret'
  'tme-token'
  'tme-app-secret'
  'farnell-api-key'
  'rs-api-key'
  'app-insights-connection-string'
  'seed-admin-email'
  'seed-admin-password'
  // Connection-string secrets referenced by Container Apps via
  // `secretRef`. Their values are populated post-deploy by the operator
  // (bootstrap.sh) — Bicep cannot compute them inline without leaking
  // the Postgres password and Redis key into the secret URL template at
  // deploy time.
  'database-url'
  'celery-broker-url'
]

// KV names are global. With purge-protection on, a deleted KV blocks
// re-creation of the same name for 90 days — fatal when re-deploying
// after a region switch. Append a deterministic 5-char hash derived from
// the RG so each (env, region) combo gets its own stable name.
var kvName = 'kv-${nameSuffix}-${take(uniqueString(resourceGroup().id), 5)}'

resource vault 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  // 'kv-ada-asm-prod-XXXXX' = 21 chars, under the 24 limit.
  name: kvName
  location: location
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled' // private endpoint deferred until we need it
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// Provision the secrets with placeholder values so the dependent
// container apps can reference them. The operator overwrites these
// post-deploy.
@batchSize(1) // serialise to avoid Key Vault rate-limit on the first deploy
resource secrets 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = [for secretName in secretNames: {
  parent: vault
  name: secretName
  properties: {
    value: 'REPLACE-ME-VIA-AZ-KEYVAULT-SECRET-SET'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}]

// ============================================================================
// Outputs
// ============================================================================

output vaultId string = vault.id
output vaultName string = vault.name
output vaultUri string = vault.properties.vaultUri

@description('List of secret names provisioned with placeholder values. The operator MUST overwrite each via `az keyvault secret set` before the dependent app starts.')
output provisionedSecretNames array = secretNames

@description('Built-in role definition ID for `Key Vault Secrets User`. Container Apps modules use this to grant the system-assigned identity read access.')
output secretsUserRoleDefinitionId string = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)
