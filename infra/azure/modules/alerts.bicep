// Application Insights alert rules.
//
// Per the spec, ONE alert ships with the change:
//   - Backend HTTP 5xx rate > 5% over 5 minutes → email ops@tierra.audio.
//
// The Action Group routes the email (and could route SMS / webhooks
// later). Both resources are global (`Microsoft.Insights/actionGroups`
// + `Microsoft.Insights/scheduledQueryRules`) but live in the same RG
// for convenience.

@allowed([
  'dev'
  'prod'
])
param environment string

param location string
param nameSuffix string

@description('Email address that receives the alert. Defaults to the project\'s ops mailbox.')
param emailAddress string = 'ops@tierra.audio'

@description('Application Insights resource ID — the alert queries this instance.')
param appInsightsId string

// ---- Action group (where the alert routes) ----

resource actionGroup 'Microsoft.Insights/actionGroups@2024-10-01-preview' = {
  // Action group names allow up to 260 chars but the SHORT NAME is
  // limited to 12.
  name: 'ag-${nameSuffix}-ops'
  location: 'global'
  properties: {
    groupShortName: take('ops${environment}', 12)
    enabled: true
    emailReceivers: [
      {
        name: 'ops-email'
        emailAddress: emailAddress
        useCommonAlertSchema: true
      }
    ]
  }
  tags: {
    project: 'ada-asm'
    environment: environment
  }
}

// ---- 5xx scheduled query rule ----
//
// Kusto query: errorRate over the last 5 minutes, fires when > 5%.
// We use a scheduled query rule (not a metric alert) because metric
// alerts don't expose a "ratio over time window" out of the box for
// custom dimensions.

resource fiveHundredAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'alert-${nameSuffix}-5xx-rate'
  location: location
  properties: {
    displayName: '[${environment}] Backend 5xx rate above 5%'
    description: 'Fires when more than 5% of backend HTTP requests return 5xx over a 5-minute window. Routes to ${emailAddress}.'
    severity: 1 // Sev 1 — high; Sev 0 reserved for "site is down"
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [
      appInsightsId
    ]
    targetResourceTypes: [
      'Microsoft.Insights/components'
    ]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where cloud_RoleName == 'ada-asm-backend'
            | summarize total = count(), errors = countif(toint(resultCode) >= 500)
            | extend errorRatePct = todouble(errors) / total * 100
            | project errorRatePct
          '''
          timeAggregation: 'Average'
          metricMeasureColumn: 'errorRatePct'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [
        actionGroup.id
      ]
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

output actionGroupId string = actionGroup.id
output fiveHundredAlertId string = fiveHundredAlert.id
