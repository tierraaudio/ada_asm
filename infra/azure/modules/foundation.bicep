// Foundation observability layer.
//
// Provisions the Log Analytics Workspace (sink for diagnostic logs from
// every other Azure resource) and the Application Insights instance
// (sink for OpenTelemetry traces, metrics, and Web SDK page views).
//
// Per the spec:
// - PerGB2018 SKU on the workspace.
// - Retention: 30 days on dev, 90 days on prod.
// - App Insights is workspace-based (the modern shape, not classic).

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

// Retention is the only thing that diverges between dev and prod.
var retentionDays = environment == 'prod' ? 90 : 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${nameSuffix}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: -1 // no cap; we rely on per-app sampling instead
    }
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${nameSuffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
    // Disable IP masking so client IPs are usable in the dashboard tiles
    // — we're not collecting PII beyond what authenticated users already
    // identify themselves with.
    DisableIpMasking: false
    // RetentionInDays here is informational; the real retention is the
    // workspace's `retentionInDays`.
    RetentionInDays: retentionDays
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ============================================================================
// Outputs
// ============================================================================

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output workspaceCustomerId string = workspace.properties.customerId

output applicationInsightsId string = appInsights.id
output applicationInsightsName string = appInsights.name

@description('The OTLP-compatible connection string the backend reads from `APPLICATIONINSIGHTS_CONNECTION_STRING` and the frontend reads from `VITE_APP_INSIGHTS_CONNECTION_STRING`.')
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString

@description('Instrumentation key (legacy). Kept exported for any tooling that has not migrated to connection strings.')
output applicationInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
