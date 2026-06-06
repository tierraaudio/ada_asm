// Container Apps Environment (Consumption profile).
//
// The Environment is the multi-tenant network boundary for all
// Container Apps + Container App Jobs. We pick Consumption (not
// Workload Profiles) because we want scale-to-zero on the worker and
// don't need dedicated nodes at our scale.
//
// Diagnostic logs stream to the Log Analytics Workspace from
// `foundation.bicep` so container stdout/stderr is queryable alongside
// the App Insights traces.

param environment string
param location string
param nameSuffix string

@description('ID of the Log Analytics Workspace used as the diagnostic sink. Pass `foundation.outputs.workspaceId`.')
param logAnalyticsWorkspaceId string

@description('Customer ID (workspace GUID) of the Log Analytics Workspace. Pass `foundation.outputs.workspaceCustomerId`.')
param logAnalyticsWorkspaceCustomerId string

// Workspace shared key is read from the workspace resource directly so
// rotating it doesn't require a redeploy.
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: split(logAnalyticsWorkspaceId, '/')[8]
}

resource environment_ 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${nameSuffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceCustomerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    // Public ingress; we rely on Container Apps' built-in custom domain
    // + managed cert per app, not a single Environment-level entry point.
    vnetConfiguration: {}
    zoneRedundant: false // single AZ on Burstable / Consumption — fine at our scale
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ============================================================================
// Outputs
// ============================================================================

output environmentId string = environment_.id
output environmentName string = environment_.name

@description('Default domain ALL Container Apps in this environment share (`<app>.<random>.westeurope.azurecontainerapps.io`). Used by `dns.bicep` to build the CNAME targets.')
output defaultDomain string = environment_.properties.defaultDomain

@description('Static outbound IP of the environment. Add this to the Postgres firewall (or use a private endpoint instead).')
output staticIp string = environment_.properties.staticIp
