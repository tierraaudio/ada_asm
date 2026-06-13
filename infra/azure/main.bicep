// ada_asm — Azure deployment entry point.
//
// Provisions the entire ada_asm stack into the resource group that the
// deployment is targeted at. The same template provisions `dev` or
// `prod` based on the `environment` parameter; SKU sizing and naming
// are derived from it.
//
// Container registry: per-environment ACR (`mod-acr` → `acradaasm<env>`)
// integrated with Container Apps' system-assigned managed identities via
// the AcrPull role (granted inside `container_apps.bicep` and
// `container_jobs.bicep`). The deploy UAMI gets AcrPush via
// `identity.bicep`. No long-lived registry credentials live in Key Vault.
//
// Usage:
//   az deployment group create \
//     --resource-group rg-ada-asm-dev \
//     --template-file infra/azure/main.bicep \
//     --parameters infra/azure/parameters.dev.bicepparam \
//     --parameters postgresAdminPassword=<from-secret-input>
//
// Preview without applying:
//   az deployment group what-if --resource-group ... --template-file ... --parameters ...

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@allowed([
  'dev'
  'prod'
])
@description('Environment name — drives SKU sizing, retention windows, and naming.')
param environment string

@description('Azure region for all resources. Defaults to the resource group\'s location.')
param location string = resourceGroup().location

@description('Short slug used in resource names.')
param projectSlug string = 'ada-asm'

@description('Apex DNS zone for the public domains.')
param dnsZoneName string = 'tierra.audio'

@description('GitHub repository in `owner/repo` form.')
param githubRepository string = 'tierraaudio/ada_asm'

@description('Branch name allowed to deploy via OIDC.')
param githubBranch string = 'main'

@description('Email address that receives the 5xx alert.')
param alertEmailAddress string = 'ops@tierra.audio'

@description('Whether to delete the legacy `ada` A record. Default false so the first deploy is reversible; set true during the documented cutover only.')
param legacyARecordCleanup bool = false

@description('Postgres admin password. Passed in via `--parameters postgresAdminPassword=...` so the literal never appears in version control.')
@secure()
param postgresAdminPassword string

@description('Backend container image. The deploy workflow overrides on every run with the real ACR tag (e.g. `acradaasmdev.azurecr.io/ada-asm-backend:<sha>`). The default placeholder lets Bicep create Container Apps before any real image is built.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

// ============================================================================
// Derived names
// ============================================================================

var nameSuffix = '${projectSlug}-${environment}'
var spaRecordName = environment == 'prod' ? 'ada' : 'ada-dev'
var apiRecordName = environment == 'prod' ? 'api.ada' : 'api.ada-dev'
var spaCustomDomain = '${spaRecordName}.${dnsZoneName}'
var apiCustomDomain = '${apiRecordName}.${dnsZoneName}'

// ============================================================================
// Foundation: Log Analytics + Application Insights
// ============================================================================

module foundation 'modules/foundation.bicep' = {
  name: 'mod-foundation'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
  }
}

// ============================================================================
// Network: Container Apps Environment
// ============================================================================

module network 'modules/network.bicep' = {
  name: 'mod-network'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    logAnalyticsWorkspaceId: foundation.outputs.workspaceId
    logAnalyticsWorkspaceCustomerId: foundation.outputs.workspaceCustomerId
  }
}

// ============================================================================
// Data: Postgres Flexible Server
// ============================================================================

module data 'modules/data.bicep' = {
  name: 'mod-data'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    adminPassword: postgresAdminPassword
    containerAppsEnvironmentStaticIp: network.outputs.staticIp
  }
}

// ============================================================================
// Redis
//
// 'Azure Cache for Redis' is being retired by Microsoft (BadRequest on new
// creates from 2026-06). 'Azure Managed Redis' (the replacement) starts at
// ≈90 €/mo for the smallest SKU. We self-host Redis as a Container App
// inside the same CAE — zero extra service cost, single-replica, internal
// ingress only. See `modules/redis.bicep` for the trade-offs.
// ============================================================================

module redis 'modules/redis.bicep' = {
  name: 'mod-redis'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    environmentId: network.outputs.environmentId
  }
}

// ============================================================================
// Storage (Celery broker queues)
//
// The Celery broker rides Azure Storage Queues, NOT the Redis above: the
// CAE internal TCP ingress proved unreliable for redis:// (June 2026 —
// healthy Redis, TCP connect timeouts from every client). Redis remains
// as the best-effort app cache only. See `modules/storage.bicep`.
// ============================================================================

module storage 'modules/storage.bicep' = {
  name: 'mod-storage'
  params: {
    environment: environment
    location: location
  }
}

// ============================================================================
// Key Vault
// ============================================================================

module keyvault 'modules/keyvault.bicep' = {
  name: 'mod-keyvault'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
  }
}

// ============================================================================
// Deploy identity (UAMI + GitHub OIDC + Contributor)
// ============================================================================

module identity 'modules/identity.bicep' = {
  name: 'mod-identity'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    githubRepository: githubRepository
    githubBranch: githubBranch
    acrId: acr.outputs.acrId
    acrPushRoleDefinitionId: acr.outputs.acrPushRoleDefinitionId
  }
}

// ============================================================================
// Azure Container Registry (per-environment)
// ============================================================================

module acr 'modules/acr.bicep' = {
  name: 'mod-acr'
  params: {
    environment: environment
    location: location
  }
}

// ============================================================================
// Long-running Container Apps: backend + worker
// ============================================================================

module containerApps 'modules/container_apps.bicep' = {
  name: 'mod-container-apps'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    environmentId: network.outputs.environmentId
    backendImage: backendImage
    workerImage: backendImage
    postgresUrlTemplate: data.outputs.connectionUrlTemplate
    redisUrlTemplate: redis.outputs.connectionUrlTemplate
    keyVaultUri: keyvault.outputs.vaultUri
    acrLoginServer: acr.outputs.loginServer
    acrId: acr.outputs.acrId
    acrPullRoleDefinitionId: acr.outputs.acrPullRoleDefinitionId
    kvId: keyvault.outputs.vaultId
    kvSecretsUserRoleDefinitionId: keyvault.outputs.secretsUserRoleDefinitionId
    // Datasheet archival storage (change `ingest-component-from-mpn`).
    datasheetStorageAccountId: storage.outputs.accountId
    datasheetBlobEndpoint: storage.outputs.blobEndpoint
    datasheetContainer: storage.outputs.datasheetContainerName
    storageBlobDataContributorRoleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    // backendCustomDomain removed — bind happens post-deploy via
    // `az containerapp hostname add/bind`. See container_apps.bicep notes.
  }
}

// ============================================================================
// One-shot jobs: migrate + seed-admin + beat-cron (KEDA)
// ============================================================================

module containerJobs 'modules/container_jobs.bicep' = {
  name: 'mod-container-jobs'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    environmentId: network.outputs.environmentId
    backendImage: backendImage
    keyVaultUri: keyvault.outputs.vaultUri
    acrLoginServer: acr.outputs.loginServer
    acrId: acr.outputs.acrId
    acrPullRoleDefinitionId: acr.outputs.acrPullRoleDefinitionId
    kvId: keyvault.outputs.vaultId
    kvSecretsUserRoleDefinitionId: keyvault.outputs.secretsUserRoleDefinitionId
  }
}

// ============================================================================
// Static Web App for the SPA
// ============================================================================

// Static Web Apps are only available in a small set of regions
// (centralus, eastus2, westus2, westeurope, eastasia). When the rest of
// the stack lands in another EU region (e.g. northeurope for AKS capacity),
// pin the SWA explicitly to westeurope so the deploy still succeeds.
var swaLocation = contains(['centralus', 'eastus2', 'westus2', 'westeurope', 'eastasia'], location) ? location : 'westeurope'

module swa 'modules/static_web_app.bicep' = {
  name: 'mod-swa'
  params: {
    environment: environment
    location: swaLocation
    nameSuffix: nameSuffix
    customDomain: spaCustomDomain
  }
}

// ============================================================================
// DNS records (CNAMEs + asuid TXT + legacy A cleanup)
// ============================================================================

module dns 'modules/dns.bicep' = {
  name: 'mod-dns'
  params: {
    environment: environment
    dnsZoneName: dnsZoneName
    spaRecordName: spaRecordName
    apiRecordName: apiRecordName
    swaDefaultHostname: swa.outputs.defaultHostname
    backendDefaultHostname: containerApps.outputs.backendFqdn
    swaValidationToken: swa.outputs.dnsValidationToken
    legacyARecordCleanup: legacyARecordCleanup
    deployScriptIdentityId: identity.outputs.identityResourceId
  }
}

// ============================================================================
// Dashboard + alert
// ============================================================================

module dashboard 'modules/dashboard.bicep' = {
  name: 'mod-dashboard'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    appInsightsId: foundation.outputs.applicationInsightsId
  }
}

module alerts 'modules/alerts.bicep' = {
  name: 'mod-alerts'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
    emailAddress: alertEmailAddress
    appInsightsId: foundation.outputs.applicationInsightsId
  }
}

// ============================================================================
// Outputs (consumed by the GitHub workflow)
// ============================================================================

@description('Environment this deployment targeted.')
output deployedEnvironment string = environment

@description('Resource group name.')
output resourceGroupName string = resourceGroup().name

@description('Suffix used for all resource names.')
output resourceNameSuffix string = nameSuffix

@description('OIDC client ID — copy into GitHub Actions variable `AZURE_CLIENT_ID`.')
output azureClientId string = identity.outputs.clientId

@description('Subscription ID — copy into GitHub Actions variable `AZURE_SUBSCRIPTION_ID`.')
output azureSubscriptionId string = subscription().subscriptionId

@description('Tenant ID — copy into GitHub Actions variable `AZURE_TENANT_ID`.')
output azureTenantId string = subscription().tenantId

@description('Application Insights connection string. Surfaced here so the FE build can inject `VITE_APP_INSIGHTS_CONNECTION_STRING` at build time.')
output applicationInsightsConnectionString string = foundation.outputs.applicationInsightsConnectionString

@description('Backend FQDN (Azure-managed). The CNAME `api.ada.tierra.audio` points at this.')
output backendDefaultHostname string = containerApps.outputs.backendFqdn

@description('SWA default hostname. The CNAME `ada.tierra.audio` points at this.')
output swaDefaultHostname string = swa.outputs.defaultHostname

@description('Public SPA URL.')
output spaUrl string = 'https://${spaCustomDomain}'

@description('Public API URL.')
output apiUrl string = 'https://${apiCustomDomain}'

@description('ACR login server. Used by the deploy workflow as `IMAGE_REGISTRY`.')
output acrLoginServer string = acr.outputs.loginServer

@description('ACR resource name (no .azurecr.io suffix). Used by the deploy workflow for `az acr login`.')
output acrName string = acr.outputs.acrName
