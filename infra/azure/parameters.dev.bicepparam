// ada_asm — dev environment parameters.
//
// Apply with:
//   az deployment group create \
//     --resource-group rg-ada-asm-dev \
//     --template-file infra/azure/main.bicep \
//     --parameters infra/azure/parameters.dev.bicepparam

using 'main.bicep'

param environment = 'dev'
param projectSlug = 'ada-asm'
param dnsZoneName = 'tierra.audio'
param githubRepository = 'tierraaudio/ada_asm'
param githubBranch = 'main'
param alertEmailAddress = 'ops@tierra.audio'

// Dev keeps the legacy A record in place — DNS cutover is a prod-only event.
param legacyARecordCleanup = false
