// Long-running Container Apps: `backend` + `worker`.
//
// Per the spec:
// - System-assigned managed identity on both apps (used to fetch Key
//   Vault secrets at revision-start time AND to pull from ACR via the
//   AcrPull role wired in acr.bicep).
// - Backend has HTTP ingress + custom domain wiring + concurrency scaler;
//   worker has no ingress + Redis-list-length scaler.
// - Both source env vars from Key Vault via `secretRef:`.
//
// The Container App Jobs (`migrate`, `seed-admin`, `beat-cron`) live in
// `container_jobs.bicep` — different resource type (`Microsoft.App/jobs`)
// with its own scaling semantics.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

@description('Container Apps Environment ID. Pass `network.outputs.environmentId`.')
param environmentId string

@description('Backend image reference, e.g. `acradaasmdev.azurecr.io/ada-asm-backend:<sha>`. The deploy workflow overrides this on every run. The default is the MCR k8se quickstart so the first Bicep deploy can create the apps before any real image exists in ACR.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Worker image — typically the same as backendImage; the worker just runs a different command.')
param workerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('ACR login server (e.g. `acradaasmdev.azurecr.io`). Used to wire the `registries[]` block with identity-based pull.')
param acrLoginServer string

@description('ACR resource ID — scope for the AcrPull role assignments.')
param acrId string

@description('Built-in AcrPull role definition ID. Granted to backend + worker system MIs on the ACR scope.')
param acrPullRoleDefinitionId string

@description('Key Vault resource ID — scope for the Key Vault Secrets User role assignments.')
param kvId string

@description('Built-in Key Vault Secrets User role definition ID. Granted to backend + worker system MIs on the KV scope so they can read secretRef values at start time.')
param kvSecretsUserRoleDefinitionId string

@description('Postgres SQLAlchemy URL. The caller fills in `{password}` with a Key Vault `secretRef:`.')
param postgresUrlTemplate string

@description('Redis URL template. The caller fills in `{key}` with a Key Vault `secretRef:`.')
param redisUrlTemplate string

@description('Vault URI used to construct `keyVaultUrl:` references for the Container App secrets block.')
param keyVaultUri string

@description('UAMI principal ID for the deploy identity. Not used directly here — Container Apps use their own system-assigned identities. Kept for cross-module wiring.')
param deployIdentityPrincipalId string = ''

// Custom-domain binding is deferred to a post-deploy step (see notes
// in the `ingress` block below).

// ---- SKU sizing ----

var backendCpu = environment == 'prod' ? '1.0' : '0.5'
var backendMemory = environment == 'prod' ? '2.0Gi' : '1.0Gi'
var backendMinReplicas = environment == 'prod' ? 1 : 0
var backendMaxReplicas = environment == 'prod' ? 5 : 3

var workerCpu = environment == 'prod' ? '0.5' : '0.25'
var workerMemory = environment == 'prod' ? '1.0Gi' : '0.5Gi'
var workerMaxReplicas = environment == 'prod' ? 3 : 2

// ---- Shared env block (backend + worker have nearly identical env vars).
// Each entry is either:
//   - { name, value } — literal value (no secret)
//   - { name, secretRef } — value read from the Container App's `secrets[]`
//                            which in turn pulls from Key Vault at start.

var sharedEnvVars = [
  { name: 'ENVIRONMENT_NAME', value: environment }
  { name: 'ENV', value: environment == 'prod' ? 'production' : 'staging' }
  { name: 'LOG_LEVEL', value: 'INFO' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker-url' }
  { name: 'CELERY_RESULT_BACKEND', secretRef: 'celery-broker-url' } // same broker, db 1 in URL — handled in main.bicep
  { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'app-insights-connection-string' }
  { name: 'CORS_ORIGINS', value: 'https://ada.tierra.audio,https://ada-dev.tierra.audio' }
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
  { name: 'SUPPLIER_LOOKUP_PRIORITY', value: 'mouser,digikey,tme,farnell,rs' }
  { name: 'SUPPLIER_LOOKUP_CACHE_TTL_SECONDS', value: '900' }
  { name: 'SUPPLIER_SYNC_DAILY_HOUR_UTC', value: '3' }
]

// ---- Container App: backend ----

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${nameSuffix}-backend'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Multiple' // blue/green
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        // CUSTOM DOMAIN BIND DEFERRED: Bicep cannot create the
        // `Microsoft.App/containerApps/customdomains/SniEnabled` binding
        // in the same deploy as the Container App itself because:
        //   1. SniEnabled requires `certificateId` of an already-issued cert.
        //   2. The managed cert can only be issued AFTER the
        //      `asuid.<host>` TXT record validates against the Container
        //      Apps Environment's verificationId.
        //   3. The Environment's verificationId is only available AFTER
        //      the Container App is created.
        //
        // Post-deploy step (see RUNBOOK_DNS_CUTOVER.md):
        //   az containerapp hostname add --resource-group $RG \
        //     --name ca-ada-asm-<env>-backend --hostname <api-fqdn>
        //   az containerapp hostname bind --resource-group $RG \
        //     --name ca-ada-asm-<env>-backend --hostname <api-fqdn> \
        //     --environment $ENV_NAME --validation-method CNAME
      }
      registries: [
        {
          // ACR pull via the Container App's system-assigned managed
          // identity. The AcrPull role assignment lives in acr.bicep.
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        // Key Vault-sourced secrets (`secretRef:` blocks above reference these).
        { name: 'jwt-secret', keyVaultUrl: '${keyVaultUri}secrets/jwt-secret', identity: 'system' }
        { name: 'database-url', keyVaultUrl: '${keyVaultUri}secrets/database-url', identity: 'system' }
        { name: 'celery-broker-url', keyVaultUrl: '${keyVaultUri}secrets/celery-broker-url', identity: 'system' }
        { name: 'app-insights-connection-string', keyVaultUrl: '${keyVaultUri}secrets/app-insights-connection-string', identity: 'system' }
        { name: 'mouser-api-key', keyVaultUrl: '${keyVaultUri}secrets/mouser-api-key', identity: 'system' }
        { name: 'digikey-client-id', keyVaultUrl: '${keyVaultUri}secrets/digikey-client-id', identity: 'system' }
        { name: 'digikey-client-secret', keyVaultUrl: '${keyVaultUri}secrets/digikey-client-secret', identity: 'system' }
        { name: 'tme-token', keyVaultUrl: '${keyVaultUri}secrets/tme-token', identity: 'system' }
        { name: 'tme-app-secret', keyVaultUrl: '${keyVaultUri}secrets/tme-app-secret', identity: 'system' }
        { name: 'farnell-api-key', keyVaultUrl: '${keyVaultUri}secrets/farnell-api-key', identity: 'system' }
        { name: 'rs-api-key', keyVaultUrl: '${keyVaultUri}secrets/rs-api-key', identity: 'system' }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json(backendCpu)
            memory: backendMemory
          }
          env: sharedEnvVars
          probes: [
            {
              // Relaxed liveness: app startup with OTel init + DB pool warmup
              // can take 30-40s. Lower values caused repeated CrashLoopBackOff
              // during prod bootstrap.
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              initialDelaySeconds: 60
              periodSeconds: 60
              timeoutSeconds: 15
              failureThreshold: 5
            }
            {
              // Relaxed readiness: the /health endpoint itself is fast (<200ms)
              // but the container event loop is briefly blocked during OTel
              // batch span exports — give it room.
              type: 'Readiness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 30
              timeoutSeconds: 10
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: backendMinReplicas
        maxReplicas: backendMaxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    role: 'backend'
  }
}

// ---- Container App: worker ----

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${nameSuffix}-worker'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single' // worker doesn't need blue/green
      // No ingress — worker is queue-driven only.
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: backend.properties.configuration.secrets // same secret list as backend
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          command: [
            'celery'
            '-A'
            'app.infrastructure.celery_app'
            'worker'
            '-l'
            'info'
          ]
          resources: {
            cpu: json(workerCpu)
            memory: workerMemory
          }
          env: sharedEnvVars
        }
      ]
      scale: {
        minReplicas: 0 // scale-to-zero; KEDA wakes us when there's work
        maxReplicas: workerMaxReplicas
        rules: [
          {
            name: 'celery-queue-depth'
            custom: {
              type: 'redis'
              metadata: {
                listName: 'celery' // default Celery queue name
                listLength: '5'
                enableTLS: 'true'
                // host comes from the broker URL secret; the scaler reads it
                // via `addressFromEnv` automatically when CELERY_BROKER_URL
                // is referenced as a secretRef on the container.
              }
              auth: [
                {
                  secretRef: 'celery-broker-url'
                  triggerParameter: 'address'
                }
              ]
            }
          }
        ]
      }
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    role: 'worker'
  }
}

// ============================================================================
// Outputs
// ============================================================================

output backendResourceId string = backend.id
output backendName string = backend.name
output backendFqdn string = backend.properties.configuration.ingress.fqdn
output backendPrincipalId string = backend.identity.principalId

output workerResourceId string = worker.id
output workerName string = worker.name
output workerPrincipalId string = worker.identity.principalId

// ============================================================================
// AcrPull role assignments
//
// Scoped to the ACR resource so backend + worker MIs can pull images.
// Lives in this module (and not main.bicep) because Bicep requires the
// role-assignment `name` expression to be calculable at deployment start,
// which means the principalId MUST come from a resource declared in the
// same module file — not from a cross-module output.
// ============================================================================

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: last(split(acrId, '/'))
}

resource backendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acrId, backend.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: backend.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acrId, worker.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: worker.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User on the KV scope so backend + worker MIs can
// resolve `secretRef:` values at revision-start time without falling back
// to a cached placeholder (which caused the dev-bootstrap CrashLoopBackOff).
resource kv 'Microsoft.KeyVault/vaults@2024-04-01-preview' existing = {
  name: last(split(kvId, '/'))
}

resource backendKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kvId, backend.id, kvSecretsUserRoleDefinitionId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleDefinitionId
    principalId: backend.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kvId, worker.id, kvSecretsUserRoleDefinitionId)
  properties: {
    roleDefinitionId: kvSecretsUserRoleDefinitionId
    principalId: worker.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
