// Redis as a Container App.
//
// Why a Container App and not Azure Cache for Redis / Azure Managed Redis:
// - Azure Cache for Redis is being retired (BadRequest on new creates from
//   2026-06 onwards). Azure Managed Redis (the official replacement) starts
//   at ≈90 €/mo for the smallest SKU.
// - Our Redis workload is small and reproducible (Celery acks_late + rate
//   limit buckets + lookup cache). Single-replica self-hosted is enough.
// - Running Redis as a Container App reuses the existing CAE compute pool —
//   no extra service cost, just CPU/RAM time within the Consumption plan.
//
// Trade-offs vs managed Redis:
// - No SLA. Restarts will lose in-flight state (acceptable: Celery acks_late
//   re-queues, rate limit buckets refill, lookup cache repopulates lazily).
// - No persistence (no AOF/RDB to disk). Same justification.
// - Internal-only ingress over TCP/6379 — no TLS, no auth (network-level
//   isolation via the CAE's internal-only ingress).

param environment string
param location string
param nameSuffix string

@description('Container Apps Environment ID. Pass `network.outputs.environmentId`. The Redis Container App lives in the same CAE as backend + worker so they reach it via the internal DNS.')
param environmentId string

@description('Redis image. Pinned to a specific minor for reproducibility.')
param redisImage string = 'docker.io/library/redis:7.4-alpine'

resource redis 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-redis-${nameSuffix}'
  location: location
  properties: {
    managedEnvironmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single' // Redis is stateful — never blue/green
      ingress: {
        external: false // internal CAE traffic only
        targetPort: 6379
        exposedPort: 6379
        transport: 'tcp'
        // No CORS / no managed cert — TCP-only.
      }
    }
    template: {
      containers: [
        {
          name: 'redis'
          image: redisImage
          // Bump default TCP keepalive so idle connections don't get dropped
          // by the CAE envoy after the default 4-hour idle timeout.
          args: [
            '--maxmemory'
            '200mb'
            '--maxmemory-policy'
            'allkeys-lru'
            '--save'
            '' // disable RDB snapshots — we don't persist
            '--appendonly'
            'no'
            '--tcp-keepalive'
            '60'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1 // Redis must always be up — KEDA cannot scale to zero on a stateful service
        maxReplicas: 1 // single-replica, no clustering
      }
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
    role: 'redis'
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Hostname of the Redis Container App, reachable from other apps in the same CAE on port 6379.')
output hostname string = redis.properties.configuration.ingress.fqdn

@description('Resource ID of the Redis Container App.')
output resourceId string = redis.id

@description('Connection URL — plaintext Redis over TCP within the CAE. No `{key}` placeholder because there is no password.')
output connectionUrlTemplate string = 'redis://${redis.properties.configuration.ingress.fqdn}:6379/0'

@description('Empty placeholder — kept for backwards-compatibility with the caller (which previously expected a key for Azure Cache for Redis). The self-hosted Redis has no auth.')
output primaryKey string = ''
