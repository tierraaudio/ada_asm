// Azure Cache for Redis (Basic C0).
//
// Per the spec + design.md:
// - Basic C0 (250 MB, no SLA) on BOTH dev and prod.
//   The original draft proposed Standard C1 for prod; we downgraded
//   because (a) no SLA target documented, (b) the data in Redis is
//   reproducible (Celery acks_late + rate-limit buckets + caches), and
//   (c) we can upgrade with a one-line parameter change later.
// - TLS-only (`enableNonSslPort: false`) — the worker connects via
//   `rediss://` exclusively.

param environment string
param location string
param nameSuffix string

resource redis 'Microsoft.Cache/Redis@2024-03-01' = {
  name: 'redis-${nameSuffix}'
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0 // C0 = 250 MB
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    redisConfiguration: {
      // `maxmemory-policy` is set to `allkeys-lru` so when we hit the
      // 250 MB cap the cache evicts the LRU entry (instead of refusing
      // writes). For the broker queues this means we'd lose tasks — but
      // at our volume we never approach the cap.
      'maxmemory-policy': 'allkeys-lru'
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ============================================================================
// Outputs
// ============================================================================

output hostname string = redis.properties.hostName
output sslPort int = redis.properties.sslPort
output resourceId string = redis.id

@description('Primary access key. Read via `listKeys()` at deploy time so it is never inlined. The caller stores it in Key Vault as `redis-primary-key`.')
output primaryKey string = redis.listKeys().primaryKey

@description('Connection URL template — the caller fills `{key}` with the Key Vault reference.')
output connectionUrlTemplate string = 'rediss://:{key}@${redis.properties.hostName}:${redis.properties.sslPort}/0'
