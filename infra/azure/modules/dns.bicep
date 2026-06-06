// DNS records in the Azure DNS zone for `tierra.audio`.
//
// Per the spec, we provision:
//   1. CNAME `ada`        → SWA default hostname
//   2. CNAME `api.ada`    → backend Container App default hostname
//   3. TXT  `asuid.ada`   → SWA managed-cert validation token
//   4. TXT  `asuid.api.ada` → ACA managed-cert validation token
// And conditionally:
//   5. DELETE the pre-existing `ada` A record pointing at 134.0.10.173
//      — only happens when `legacyARecordCleanup=true` (set during
//      cutover per the runbook).
//
// The Azure DNS zone `tierra.audio` is assumed to already exist in this
// subscription. We do NOT provision the zone itself (it predates this
// change).

@allowed([
  'dev'
  'prod'
])
param environment string

@description('Apex DNS zone name. Defaults to `tierra.audio`.')
param dnsZoneName string = 'tierra.audio'

@description('SPA subdomain record name. `ada` on prod, `ada-dev` on dev.')
param spaRecordName string

@description('API subdomain record name. `api.ada` on prod, `api.ada-dev` on dev.')
param apiRecordName string

@description('Default Azure hostname of the Static Web App. Pass `swa.outputs.defaultHostname`.')
param swaDefaultHostname string

@description('Default Azure hostname of the backend Container App. Pass `containerApps.outputs.backendFqdn`.')
param backendDefaultHostname string

@description('Managed-cert validation token emitted by the SWA. Pass `swa.outputs.dnsValidationToken`.')
param swaValidationToken string

@description('Set to true ONLY during the cutover step. When true, the pre-existing `ada` A record is deleted from the zone.')
param legacyARecordCleanup bool = false

// Reference the existing zone — we don't create it.
resource zone 'Microsoft.Network/dnsZones@2018-05-01' existing = {
  name: dnsZoneName
}

// ============================================================================
// SPA: CNAME ada → SWA
// ============================================================================

resource spaCname 'Microsoft.Network/dnsZones/CNAME@2018-05-01' = {
  parent: zone
  name: spaRecordName
  properties: {
    TTL: 300
    CNAMERecord: {
      cname: swaDefaultHostname
    }
    metadata: {
      managedBy: 'bicep'
      project: 'ada-asm'
      environment: environment
    }
  }
}

// Managed-cert validation token TXT — at `asuid.<spaRecordName>`.
resource spaAsuidTxt 'Microsoft.Network/dnsZones/TXT@2018-05-01' = {
  parent: zone
  name: 'asuid.${spaRecordName}'
  properties: {
    TTL: 300
    TXTRecords: [
      {
        value: [
          swaValidationToken
        ]
      }
    ]
    metadata: {
      managedBy: 'bicep'
      project: 'ada-asm'
      environment: environment
      purpose: 'swa-managed-cert-validation'
    }
  }
}

// ============================================================================
// API: CNAME api.ada → backend Container App
// ============================================================================

resource apiCname 'Microsoft.Network/dnsZones/CNAME@2018-05-01' = {
  parent: zone
  name: apiRecordName
  properties: {
    TTL: 300
    CNAMERecord: {
      cname: backendDefaultHostname
    }
    metadata: {
      managedBy: 'bicep'
      project: 'ada-asm'
      environment: environment
    }
  }
}

// The Container Apps managed-cert validation token. Unlike SWA, ACA
// publishes the token AFTER the custom-domain resource is created on
// the app side — this asuid TXT can be added pre-emptively with a
// placeholder, and re-applied with the real token once the ACA
// custom-domain reports the value. For the first deploy we use the
// `verificationId` from the Container Apps Environment, which is the
// stable value Azure expects.
//
// This module accepts the ACA verification ID as a parameter so we keep
// the dependency direction container_apps → dns unidirectional.

@description('ACA Environment custom-domain verification ID. Pass `network.outputs.environmentId` resolved via `properties.customDomainConfiguration.customDomainVerificationId`. The caller in main.bicep wires this.')
param acaVerificationId string = ''

resource apiAsuidTxt 'Microsoft.Network/dnsZones/TXT@2018-05-01' = if (!empty(acaVerificationId)) {
  parent: zone
  name: 'asuid.${apiRecordName}'
  properties: {
    TTL: 300
    TXTRecords: [
      {
        value: [
          acaVerificationId
        ]
      }
    ]
    metadata: {
      managedBy: 'bicep'
      project: 'ada-asm'
      environment: environment
      purpose: 'aca-managed-cert-validation'
    }
  }
}

// ============================================================================
// Legacy A record cleanup
// ============================================================================
//
// The pre-existing A record `ada → 134.0.10.173` is a legacy redirect
// to tierraaudio.com. Per the user it's disposable. We DON'T model the
// deletion as a Bicep "remove" resource (Bicep is declarative-only and
// can't express "delete this thing that's outside my template");
// instead, the cutover runbook walks the operator through an
// `az network dns record-set delete` invocation, gated on this flag.
//
// We DO emit a deployment-script that runs the delete idempotently when
// `legacyARecordCleanup=true`. This way the same `az deployment` flow
// handles both the additions AND the legacy cleanup.

resource cleanupScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = if (legacyARecordCleanup) {
  name: 'ds-cleanup-legacy-a-${environment}'
  location: resourceGroup().location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${deployScriptIdentityId}': {}
    }
  }
  properties: {
    azCliVersion: '2.60.0'
    timeout: 'PT15M'
    retentionInterval: 'PT1H'
    scriptContent: '''
      set -euo pipefail
      EXISTING=$(az network dns record-set a show \
        --resource-group "$ZONE_RG" \
        --zone-name "$ZONE" \
        --name "$RECORD_NAME" \
        --query "id" -o tsv 2>/dev/null || echo "")
      if [ -n "$EXISTING" ]; then
        echo "Found legacy A record at $RECORD_NAME.$ZONE — deleting"
        az network dns record-set a delete \
          --resource-group "$ZONE_RG" \
          --zone-name "$ZONE" \
          --name "$RECORD_NAME" --yes
      else
        echo "No legacy A record at $RECORD_NAME.$ZONE — nothing to do"
      fi
    '''
    environmentVariables: [
      { name: 'ZONE', value: dnsZoneName }
      { name: 'ZONE_RG', value: resourceGroup().name }
      { name: 'RECORD_NAME', value: spaRecordName }
    ]
  }
}

@description('UAMI resource ID used by the cleanup script. Pass `identity.outputs.identityResourceId` from the deploy identity module.')
param deployScriptIdentityId string = ''

// ============================================================================
// Outputs
// ============================================================================

output spaFqdn string = '${spaRecordName}.${dnsZoneName}'
output apiFqdn string = '${apiRecordName}.${dnsZoneName}'
