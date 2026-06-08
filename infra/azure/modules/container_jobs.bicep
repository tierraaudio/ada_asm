// Container App Jobs: migrate + seed-admin + beat-cron.
//
// Per the spec:
// - `migrate` runs `alembic upgrade head` once, invoked by the deploy
//   workflow BEFORE promoting a new backend revision. Trigger type:
//   `Manual` (workflow_dispatch via `az containerapp job start`).
// - `seed-admin` runs `python -m app.scripts.seed_admin` once with the
//   email + password sourced from Key Vault. Trigger type: `Manual`.
// - `beat-cron` runs `python -m app.scripts.cron_run_daily_sync` on a
//   KEDA cron schedule (default `0 3 * * *`). REPLACES the long-running
//   Celery Beat container — this is the whole point of the cloud
//   migration's "no idle Beat process" goal.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

@description('Container Apps Environment ID. Pass `network.outputs.environmentId`.')
param environmentId string

@description('Backend image reference shared with the long-running apps. Migrations + cron run against the same image because the entry-point scripts live in the backend container. The default is the MCR k8se quickstart placeholder so the first Bicep deploy can create the jobs before any real image exists in ACR.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Key Vault URI to construct `keyVaultUrl:` references.')
param keyVaultUri string

@description('ACR login server (e.g. `acradaasmdev.azurecr.io`). Each Job pulls via its own system MI; AcrPull is granted below.')
param acrLoginServer string

@description('ACR resource ID — scope for the AcrPull role assignments.')
param acrId string

@description('Built-in AcrPull role definition ID. Granted to each Job system MI on the ACR scope.')
param acrPullRoleDefinitionId string

@description('Key Vault resource ID — scope for the Key Vault Secrets User role assignments.')
param kvId string

@description('Built-in Key Vault Secrets User role definition ID. Granted to each Job system MI so it can resolve `secretRef:` values at start time.')
param kvSecretsUserRoleDefinitionId string

@description('Cron expression for the daily sync. Default 03:00 UTC.')
param dailySyncCron string = '0 3 * * *'

// Shared secret block — every job runs the backend image so each has
// the same env requirements as the long-running backend container.
var sharedSecrets = [
  { name: 'database-url', keyVaultUrl: '${keyVaultUri}secrets/database-url', identity: 'system' }
  { name: 'celery-broker-url', keyVaultUrl: '${keyVaultUri}secrets/celery-broker-url', identity: 'system' }
  { name: 'jwt-secret', keyVaultUrl: '${keyVaultUri}secrets/jwt-secret', identity: 'system' }
  { name: 'app-insights-connection-string', keyVaultUrl: '${keyVaultUri}secrets/app-insights-connection-string', identity: 'system' }
  { name: 'mouser-api-key', keyVaultUrl: '${keyVaultUri}secrets/mouser-api-key', identity: 'system' }
  { name: 'digikey-client-id', keyVaultUrl: '${keyVaultUri}secrets/digikey-client-id', identity: 'system' }
  { name: 'digikey-client-secret', keyVaultUrl: '${keyVaultUri}secrets/digikey-client-secret', identity: 'system' }
  { name: 'tme-token', keyVaultUrl: '${keyVaultUri}secrets/tme-token', identity: 'system' }
  { name: 'tme-app-secret', keyVaultUrl: '${keyVaultUri}secrets/tme-app-secret', identity: 'system' }
  { name: 'farnell-api-key', keyVaultUrl: '${keyVaultUri}secrets/farnell-api-key', identity: 'system' }
  { name: 'rs-api-key', keyVaultUrl: '${keyVaultUri}secrets/rs-api-key', identity: 'system' }
  { name: 'seed-admin-email', keyVaultUrl: '${keyVaultUri}secrets/seed-admin-email', identity: 'system' }
  { name: 'seed-admin-password', keyVaultUrl: '${keyVaultUri}secrets/seed-admin-password', identity: 'system' }
]

var sharedRegistries = [
  {
    // ACR pull via each Job's system-assigned managed identity.
    // AcrPull role on the ACR scope is wired in acr.bicep.
    server: acrLoginServer
    identity: 'system'
  }
]

var baseEnvVars = [
  { name: 'ENVIRONMENT_NAME', value: environment }
  { name: 'ENV', value: environment == 'prod' ? 'production' : 'staging' }
  { name: 'LOG_LEVEL', value: 'INFO' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker-url' }
  { name: 'CELERY_RESULT_BACKEND', secretRef: 'celery-broker-url' }
  { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'app-insights-connection-string' }
  { name: 'MOUSER_API_KEY', secretRef: 'mouser-api-key' }
  { name: 'DIGIKEY_CLIENT_ID', secretRef: 'digikey-client-id' }
  { name: 'DIGIKEY_CLIENT_SECRET', secretRef: 'digikey-client-secret' }
  { name: 'DIGIKEY_OAUTH_TOKEN_URL', value: 'https://api.digikey.com/v1/oauth2/token' }
  { name: 'TME_TOKEN', secretRef: 'tme-token' }
  { name: 'TME_APP_SECRET', secretRef: 'tme-app-secret' }
  { name: 'FARNELL_API_KEY', secretRef: 'farnell-api-key' }
  { name: 'FARNELL_STORE_ID', value: 'es.farnell.com' }
  { name: 'RS_API_KEY', secretRef: 'rs-api-key' }
  { name: 'SUPPLIER_SYNC_ENABLED_SUPPLIERS', value: 'mouser,digikey,tme,farnell' }
]

// ============================================================================
// 1. Migration job
// ============================================================================

resource migrateJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-${nameSuffix}-migrate'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800 // 30 min hard cap; Alembic almost always finishes in <60s
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: sharedRegistries
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: backendImage
          command: [
            'alembic'
            'upgrade'
            'head'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: baseEnvVars
        }
      ]
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    purpose: 'alembic-migrate'
  }
}

// ============================================================================
// 2. Seed admin job
// ============================================================================

resource seedAdminJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-${nameSuffix}-seed-admin'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 300
      replicaRetryLimit: 0 // idempotency check in the script — no retry
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: sharedRegistries
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'seed-admin'
          image: backendImage
          command: [
            'python'
            '-m'
            'app.scripts.seed_admin'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat(baseEnvVars, [
            { name: 'SEED_ADMIN_EMAIL', secretRef: 'seed-admin-email' }
            { name: 'SEED_ADMIN_PASSWORD', secretRef: 'seed-admin-password' }
          ])
        }
      ]
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    purpose: 'seed-admin'
  }
}

// ============================================================================
// 3. Daily sync cron job (replaces Celery Beat)
// ============================================================================

resource beatCronJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'caj-${nameSuffix}-beat-cron'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 3600 // 1 hour hard cap; the daily sync usually finishes in <5min per supplier
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: dailySyncCron
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: sharedRegistries
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'beat-cron'
          image: backendImage
          command: [
            'python'
            '-m'
            'app.scripts.cron_run_daily_sync'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: baseEnvVars
        }
      ]
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    purpose: 'daily-supplier-sync'
  }
}

// ============================================================================
// Outputs
// ============================================================================

output migrateJobName string = migrateJob.name
output migrateJobPrincipalId string = migrateJob.identity.principalId

output seedAdminJobName string = seedAdminJob.name
output seedAdminJobPrincipalId string = seedAdminJob.identity.principalId

output beatCronJobName string = beatCronJob.name
output beatCronJobPrincipalId string = beatCronJob.identity.principalId

@description('Convenience: command line to start the migrate job from the deploy workflow.')
output migrateJobStartCommand string = 'az containerapp job start --name ${migrateJob.name} --resource-group <rg>'

// ============================================================================
// AcrPull role assignments per Job
// ============================================================================

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: last(split(acrId, '/'))
}

resource migrateJobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acrId, migrateJob.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: migrateJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource seedAdminJobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acrId, seedAdminJob.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: seedAdminJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource beatCronJobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acrId, beatCronJob.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: beatCronJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User on the KV scope so each Job's MI can resolve
// secretRef values at start. Required for migrate / seed-admin / beat-cron
// to read DATABASE_URL etc. (See container_apps.bicep for the same pattern.)
resource kv 'Microsoft.KeyVault/vaults@2024-04-01-preview' existing = {
  name: last(split(kvId, '/'))
}

resource migrateJobKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kvId, migrateJob.id, kvSecretsUserRoleDefinitionId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleDefinitionId
    principalId: migrateJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource seedAdminJobKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kvId, seedAdminJob.id, kvSecretsUserRoleDefinitionId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleDefinitionId
    principalId: seedAdminJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource beatCronJobKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kvId, beatCronJob.id, kvSecretsUserRoleDefinitionId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleDefinitionId
    principalId: beatCronJob.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
