// Storage account serving two jobs:
//  1. Celery broker queues (kombu `azurestoragequeues` transport). Added
//     after the CAE internal TCP ingress proved unreliable for redis://
//     (June 2026). Storage Queues are HTTP-based, no TCP ingress involved.
//  2. Archived datasheet PDFs (private `datasheets` blob container),
//     consumed by the ingestion pipeline (change `ingest-component-from-mpn`).
//     The backend reads/writes via its managed identity (Storage Blob Data
//     Contributor role assigned in container_apps.bicep), never an account
//     key — the container has NO anonymous public access.
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

// Private blob container for archived datasheet PDFs (no public access).
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource datasheetsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'datasheets'
  properties: {
    publicAccess: 'None'
  }
}

output accountName string = storageAccount.name
output accountId string = storageAccount.id
output queueEndpoint string = storageAccount.properties.primaryEndpoints.queue
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output datasheetContainerName string = datasheetsContainer.name
