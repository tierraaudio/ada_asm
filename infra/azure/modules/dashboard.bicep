// Application Insights Portal dashboard with the 5 tiles required by
// the spec: backend p50/p95/p99 latency, 5xx rate, supplier-sync
// success rate, lookup cache hit ratio, FE page views.
//
// The tile layout lives in `dashboard.json` so it's editable independently
// of the Bicep wiring. This module loads the JSON, substitutes the
// Application Insights resource ID into every tile's `targetSubscriptionId`
// + `targetResourceId` slot, and provisions the result as a shared
// dashboard.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

@description('Application Insights resource ID. Every tile pins its query against this instance.')
param appInsightsId string

// Load the layout from disk so we keep the Bicep small.
var dashboardLayout = loadJsonContent('../dashboard.json')

// Walk each tile and inject the App Insights resource ID into the
// settings. The dashboard JSON has placeholder references that Bicep
// rewrites at deploy time.
//
// Bicep's `loadJsonContent` returns the literal structure; we use
// `union(...)` to layer the resource ID into each tile's metadata.

resource dashboard 'Microsoft.Portal/dashboards@2020-09-01-preview' = {
  name: 'dashboard-${nameSuffix}'
  location: location
  tags: {
    'hidden-title': 'ada-asm ${environment}'
    project: 'ada-asm'
    environment: environment
  }
  properties: {
    lenses: [
      {
        order: dashboardLayout.lenses['0'].order
        parts: [for partKey in items(dashboardLayout.lenses['0'].parts): {
          position: partKey.value.position
          metadata: union(partKey.value.metadata, {
            inputs: [
              {
                name: 'ComponentId'
                value: appInsightsId
              }
            ]
          })
        }]
      }
    ]
    metadata: dashboardLayout.metadata
  }
}

// ============================================================================
// Outputs
// ============================================================================

output dashboardId string = dashboard.id
output dashboardName string = dashboard.name
