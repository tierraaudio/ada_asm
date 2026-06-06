// ada_asm — prod environment parameters.
//
// Apply with:
//   az deployment group create \
//     --resource-group rg-ada-asm-prod \
//     --template-file infra/azure/main.bicep \
//     --parameters infra/azure/parameters.prod.bicepparam
//
// CUTOVER NOTE: the first prod deploy MUST run with
// `legacyARecordCleanup = false` so the existing `ada.tierra.audio` A
// record stays in place and the rollback path is intact. Only flip this
// to `true` during the documented DNS cutover (see RUNBOOK_DNS_CUTOVER.md).

using 'main.bicep'

param environment = 'prod'
param projectSlug = 'ada-asm'
param dnsZoneName = 'tierra.audio'
param githubRepository = 'tierraaudio/ada_asm'
param githubBranch = 'main'
param alertEmailAddress = 'ops@tierra.audio'

// SET TO `true` ONLY DURING THE DNS CUTOVER STEP. See RUNBOOK_DNS_CUTOVER.md.
param legacyARecordCleanup = false
