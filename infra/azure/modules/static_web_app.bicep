// Static Web App for the React/Vite SPA.
//
// Per the spec:
// - Free tier on dev, Standard on prod (the Standard tier unlocks
//   custom auth + larger bandwidth quotas; Free is enough for dev).
// - Connected to the GitHub repo so the SWA's auto-generated workflow
//   handles the build. The Bicep doesn't need to manage that workflow
//   — it lives at `.github/workflows/azure-static-web-apps-*.yml` and
//   is auto-edited by Azure when SWA is created.
// - Custom domain wiring happens here; the actual DNS CNAME is in
//   `dns.bicep`.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

@description('GitHub repository URL (https form). The SWA pulls source from here.')
param githubRepositoryUrl string = 'https://github.com/tierraaudio/ada_asm'

@description('Branch the SWA tracks for production deploys.')
param githubBranch string = 'main'

@description('Custom domain to bind. E.g. `ada.tierra.audio` on prod, `ada-dev.tierra.audio` on dev.')
param customDomain string

// SWA Free tier supports custom domains in all regions; Standard adds
// staging environments and auth providers.
var skuName = environment == 'prod' ? 'Standard' : 'Free'

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: 'stapp-${nameSuffix}'
  // Static Web Apps must be deployed to one of a small set of regions.
  // `westeurope` works.
  location: location
  sku: {
    name: skuName
    tier: skuName
  }
  properties: {
    repositoryUrl: githubRepositoryUrl
    branch: githubBranch
    // Public access enabled. Restrictions (preview env auth, etc.) are
    // configured in `staticwebapp.config.json` at the repo root.
    publicNetworkAccess: 'Enabled'
    buildProperties: {
      appLocation: 'frontend'
      apiLocation: '' // we don't use SWA Functions — backend is on Container Apps
      outputLocation: 'dist'
      appBuildCommand: 'pnpm install && pnpm run build'
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// Bind the custom domain. The actual CNAME + asuid TXT records are
// created in `dns.bicep` — the binding here tells Azure to issue a
// managed cert for the domain.
resource customDomainBinding 'Microsoft.Web/staticSites/customDomains@2023-12-01' = {
  parent: swa
  name: customDomain
  properties: {
    // `dns-txt-token` is the cert-issuance flow — Azure publishes a
    // validation token that we ALSO publish as a `asuid.<domain>` TXT
    // record in the Azure DNS zone. Once Azure sees the matching TXT,
    // it issues the cert.
    validationMethod: 'dns-txt-token'
  }
}

// ============================================================================
// Outputs
// ============================================================================

output resourceId string = swa.id
output name string = swa.name

@description('Default Azure-managed hostname. Used as the CNAME target for `ada.tierra.audio`.')
output defaultHostname string = swa.properties.defaultHostname

@description('DNS validation token. Publish this as a TXT record at `asuid.<customDomain>` to complete cert issuance.')
output dnsValidationToken string = customDomainBinding.properties.validationToken

@description('SWA deployment token. Stored in Key Vault as `swa-deployment-token`; the GitHub workflow reads it for the SWA deploy step.')
output deploymentToken string = swa.listSecrets().properties.apiKey
