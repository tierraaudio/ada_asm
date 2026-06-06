// Long-running Container Apps: `backend` + `worker`.
//
// Per the spec:
// - System-assigned managed identity on both apps (used to fetch Key
//   Vault secrets at revision-start time).
// - GHCR pull credential (one PAT shared between the two apps).
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

@description('Backend image reference, e.g. `ghcr.io/tierraaudio/ada-asm-backend:<sha>`. The deploy workflow overrides this on every run. The default is the MCR k8se quickstart so the first Bicep deploy can create the apps before any real image exists in GHCR.')
param backendImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Worker image — typically the same as backendImage; the worker just runs a different command.')
param workerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

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
          server: 'ghcr.io'
          username: 'tierraaudio-bot' // service account username; the PAT is the secret
          passwordSecretRef: 'ghcr-pull-token'
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
        { name: 'ghcr-pull-token', keyVaultUrl: '${keyVaultUri}secrets/ghcr-pull-token', identity: 'system' }
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
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
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
          server: 'ghcr.io'
          username: 'tierraaudio-bot'
          passwordSecretRef: 'ghcr-pull-token'
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
