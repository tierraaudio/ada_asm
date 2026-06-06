// GitHub Actions OIDC federated identity.
//
// Per the spec:
// - NO long-lived service principal client secret anywhere.
// - GitHub Actions exchanges its short-lived OIDC token for an Azure
//   access token at runtime via Workload Identity Federation.
// - The Federated Identity Credential's subject claim is scoped to a
//   specific repo + branch; PRs from forks cannot deploy.
//
// This module provisions:
//   1. A User-Assigned Managed Identity dedicated to deploys.
//   2. A Federated Identity Credential linking the UAMI to the GitHub
//      repository + branch.
//   3. A Contributor role assignment scoped to the resource group.
//
// The UAMI's `clientId` is OUTPUT and the GitHub workflow uses it (plus
// the tenant + subscription IDs, which are NOT secrets) in the
// `azure/login@v2` step. No secrets persist anywhere.

param environment string
param location string
param nameSuffix string

@description('GitHub repository in `owner/repo` form. The OIDC subject claim becomes `repo:<owner/repo>:ref:refs/heads/<branch>`.')
param githubRepository string

@description('Branch name allowed to deploy via OIDC. PR / fork pushes are NOT eligible.')
param githubBranch string

// User-Assigned Managed Identity for the deploys.
resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-deploy-${nameSuffix}'
  location: location
  tags: {
    project: 'ada-asm'
    environment: environment
    purpose: 'github-actions-deploy'
  }
}

// Federated Identity Credential — the OIDC trust relationship.
resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-${githubBranch}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepository}:ref:refs/heads/${githubBranch}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

// Federated credential for `workflow_dispatch` runs from `main` — same
// subject, but Actions emits `repo:<owner/repo>:ref:refs/heads/<branch>`
// for manual runs too as long as the dispatch came from that branch.
// This is implicit in the entry above; we keep one entry for clarity.

// Grant Contributor on the resource group so the deploy can create
// every resource the Bicep template needs. Contributor explicitly does
// NOT grant role assignment privileges (User Access Administrator is
// needed for that) — and we want that boundary so the deploy can't
// escalate its own permissions.
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: resourceGroup()
  name: guid(resourceGroup().id, deployIdentity.id, 'Contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b24988ac-6180-42a0-ab88-20f7382dd24c' // Contributor
    )
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('UAMI client ID (a GUID). Copy into the GitHub repo Actions VARIABLES (not secrets) as `AZURE_CLIENT_ID` — the `azure/login@v2` action reads it.')
output clientId string = deployIdentity.properties.clientId

@description('UAMI principal ID. Used by other Bicep modules (e.g. keyvault role assignment) to grant the deploy identity additional permissions if needed.')
output principalId string = deployIdentity.properties.principalId

@description('UAMI resource ID — useful for `az identity show` debugging.')
output identityResourceId string = deployIdentity.id

@description('The exact OIDC subject claim the GitHub workflow runs as. Useful for debugging when adding new branches.')
output expectedOidcSubject string = 'repo:${githubRepository}:ref:refs/heads/${githubBranch}'
