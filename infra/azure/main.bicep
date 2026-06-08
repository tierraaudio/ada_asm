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
// ============================================================================

module redis 'modules/redis.bicep' = {
  name: 'mod-redis'
  params: {
    environment: environment
    location: location
    nameSuffix: nameSuffix
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

module swa 'modules/static_web_app.bicep' = {
  name: 'mod-swa'
  params: {
    environment: environment
    location: location
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
