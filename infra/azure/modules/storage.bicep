// Storage account whose ONLY job is to carry the Celery broker queues
// (kombu `azurestoragequeues` transport). Introduced after the CAE
// internal TCP ingress proved unreliable for redis:// (June 2026:
// healthy Redis Container App, TCP connect timeouts from every client,
// fresh app + fresh exposed port included). Storage Queues are
// HTTP-based, so no TCP ingress is involved anywhere.
//
// The broker URL consumed by the apps is:
//   azurestoragequeues://{account key}@{account}.queue.core.windows.net
// stored as the `celery-broker-url` Key Vault / Container App secret.
// NOTE: the secret VALUE is set operationally (az keyvault secret set +
// az containerapp secret set), NOT here — keyvault.bicep only seeds
// placeholders and must never overwrite live values.

@description('Deployment location. Inherits the resource group location.')
param location string = resourceGroup().location

@description('Environment suffix used in resource names, e.g. `prod`.')
param environment string

@description('Tags applied to the storage account.')
param tags object = {}

// Storage account names: 3-24 chars, lowercase alphanumeric only.
var accountName = 'stadaasmprod${take(uniqueString(resourceGroup().id), 6)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: environment == 'prod' ? accountName : 'stadaasm${environment}${take(uniqueString(resourceGroup().id), 6)}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

output accountName string = storageAccount.name
output queueEndpoint string = storageAccount.properties.primaryEndpoints.queue
