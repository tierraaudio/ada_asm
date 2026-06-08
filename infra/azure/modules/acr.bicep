// Azure Container Registry (Basic SKU) — per-environment.
//
// Why ACR (and not GHCR):
// - Container Apps can pull via system-assigned managed identity (AcrPull
//   role) — no PAT, no Key Vault secret, no cache invalidation dance.
// - Same region as Container Apps Environment ⇒ no cross-region egress
//   charges on pulls.
// - Basic SKU ≈ €4/mo + 10 GB storage, comfortable inside the €35/mo dev
//   floor.
//
// Naming: ACR names must be globally unique and alphanumeric (no
// hyphens). We use `acradaasm<env>` (e.g. `acradaasmdev`). If a global
// collision ever occurs, the `nameSuffix` param can be overridden by the
// caller to inject a `uniqueString(rg.id)` suffix without breaking the
// existing live registry — name collision is a deploy-time concern,
// resolvable without a code change.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string

@description('ACR resource name. Must be globally unique, alphanumeric, 5-50 chars. Default: `acradaasm<env>`. Caller may override (e.g. with a uniqueString suffix) if the default collides globally.')
param acrName string = 'acradaasm${environment}'

// ============================================================================
// ACR resource
// ============================================================================

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    // Admin user is the legacy password-based auth path. We use MI auth
    // only — disable the admin user so the password surface doesn't even
    // exist for an attacker to target.
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled' // private endpoint deferred (would require Premium SKU)
    zoneRedundancy: 'Disabled' // Basic SKU does not support zone redundancy
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Login server hostname, e.g. `acradaasmdev.azurecr.io`. Used by Container Apps `registries[].server` and by the GitHub workflow.')
output loginServer string = registry.properties.loginServer

@description('Full Azure resource ID — used as scope for AcrPull / AcrPush role assignments.')
output acrId string = registry.id

@description('ACR resource name (without the .azurecr.io suffix). Used by `az acr login --name <acrName>` in CI.')
output acrName string = registry.name

@description('Built-in role definition ID for `AcrPull`. Container Apps and Jobs need this on the ACR scope to pull via system MI.')
output acrPullRoleDefinitionId string = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

@description('Built-in role definition ID for `AcrPush`. The deploy UAMI needs this so the GitHub workflow can push.')
output acrPushRoleDefinitionId string = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)
