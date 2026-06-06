// Postgres Flexible Server.
//
// Per the spec:
// - Postgres 16.
// - Burstable B1ms on dev, B2s on prod.
// - Geo-redundant backups on prod, locally-redundant on dev.
// - SSL required for all connections.
// - Extensions enabled at server creation: pgcrypto, ltree, pg_stat_statements.
// - HA disabled (we don't have an SLA target).
//
// SECURITY NOTE: This module accepts the admin password as a `@secure()`
// parameter. The caller (main.bicep) reads it from a Key Vault secret
// reference at deploy time so the literal password never appears in the
// Bicep template, in `az` command-line history, or in deployment logs.

param environment string
param location string
param nameSuffix string

@description('Admin login name for the Postgres server. NOT the application user — that one is created in a follow-up migration step.')
param adminLogin string = 'adaasm_admin'

@description('Admin password. Sourced from Key Vault by the caller. Never inlined in parameter files.')
@secure()
param adminPassword string

@description('Database name to create on the server. The application connection string targets this database.')
param databaseName string = 'ada_asm'

// SKU + tier + backup retention diverge between dev and prod.
var serverConfig = environment == 'prod' ? {
  skuName: 'Standard_B2s'
  tier: 'Burstable'
  storageGb: 32
  backupRetentionDays: 14
  geoRedundantBackup: 'Enabled'
} : {
  skuName: 'Standard_B1ms'
  tier: 'Burstable'
  storageGb: 32
  backupRetentionDays: 7
  geoRedundantBackup: 'Disabled'
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: 'pg-${nameSuffix}'
  location: location
  sku: {
    name: serverConfig.skuName
    tier: serverConfig.tier
  }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: serverConfig.storageGb
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: serverConfig.backupRetentionDays
      geoRedundantBackup: serverConfig.geoRedundantBackup
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      // Public network access ON (no private endpoint at this scale).
      // The Container Apps Environment's static outbound IP is whitelisted
      // via the firewall_rules child resource below.
      publicNetworkAccess: 'Enabled'
    }
    authConfig: {
      passwordAuth: 'Enabled'
      // Active Directory auth could be added later; for now plain
      // password auth is the simplest path from local-dev parity.
      activeDirectoryAuth: 'Disabled'
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ---- Server-level configuration: enable extensions + require SSL. ----
//
// Extensions are enabled by listing them in `azure.extensions`. The
// migrations (`gen_random_uuid()` and the planned `ltree` on Module.path)
// fail without these.

resource extensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgres
  name: 'azure.extensions'
  properties: {
    value: 'PGCRYPTO,LTREE,PG_STAT_STATEMENTS'
    source: 'user-override'
  }
}

resource requireSecureTransport 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgres
  name: 'require_secure_transport'
  properties: {
    value: 'ON'
    source: 'user-override'
  }
  // Ensure the extensions config commits first — Postgres restart is
  // serial per config change.
  dependsOn: [
    extensions
  ]
}

// ---- Database ----

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgres
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// ---- Firewall rules ----
//
// The Container Apps Environment's outbound IP is whitelisted by the
// caller (main.bicep) via the `containerAppsEnvironmentStaticIp`
// parameter so we can keep this module independent of the ACA module.

@description('Static outbound IP of the Container Apps Environment. Pass `network.outputs.staticIp`.')
param containerAppsEnvironmentStaticIp string

resource firewallAca 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'allow-container-apps-environment'
  properties: {
    startIpAddress: containerAppsEnvironmentStaticIp
    endIpAddress: containerAppsEnvironmentStaticIp
  }
}

// Allow Azure-internal services (e.g. the Container App Job for
// migrations sometimes goes through a different egress IP than the apps
// themselves). The "allow Azure services" wildcard is 0.0.0.0/0.0.0.0
// — not ideal long-term but acceptable given SSL is required + auth is
// password-based.
resource firewallAzureServices 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'allow-azure-services'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ============================================================================
// Outputs
// ============================================================================

output serverFqdn string = postgres.properties.fullyQualifiedDomainName
output serverName string = postgres.name
output databaseName string = database.name

@description('SQLAlchemy/asyncpg-ready connection URL (password placeholder — the caller injects the Key Vault reference at Container Apps env var time).')
output connectionUrlTemplate string = 'postgresql+asyncpg://${adminLogin}:{password}@${postgres.properties.fullyQualifiedDomainName}:5432/${database.name}?ssl=require'
