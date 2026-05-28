// main.bicep — Virtual Try-On: ACR + Key Vault + Container Apps Environment + Container App
// Deploy at resource-group scope:
//   az deployment group create -g <rg> -f infra/main.bicep -p infra/parameters.bicepparam

@description('Location for all resources')
param location string = resourceGroup().location

@description('Short environment tag (e.g. prod)')
param environmentName string = 'prod'

@description('Container image to deploy (e.g. myacr.azurecr.io/virtual-tryon:latest)')
param containerImage string

@description('Azure AI Foundry base URL')
param azureBaseUrl string

@description('Azure AI Foundry API key')
@secure()
param azureApiKey string

@description('Flask secret key')
@secure()
param secretKey string = uniqueString(resourceGroup().id)

param azureFluxFillModel string = 'flux-pro-v1.1-fill'
param azureVisionModel   string = 'gpt-5.4-mini'
param fluxImageSize      string = '1024x1536'

var appName = 'virtual-tryon'
var tags    = { app: appName, env: environmentName }

// ── Container Registry ────────────────────────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${replace(appName, '-', '')}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// ── Key Vault ─────────────────────────────────────────────────────────────────
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${appName}-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource kvSecretApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'AZURE-API-KEY'
  properties: { value: azureApiKey }
}

resource kvSecretFlaskKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'SECRET-KEY'
  properties: { value: secretKey }
}

// ── Log Analytics (required by Container Apps) ────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${appName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ── Container Apps Environment ────────────────────────────────────────────────
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${appName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ── Managed Identity for the Container App ────────────────────────────────────
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${appName}'
  location: location
  tags: tags
}

// Grant identity: AcrPull on ACR
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant identity: Key Vault Secrets User
resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, identity.id, 'kv-secrets-user')
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Container App ─────────────────────────────────────────────────────────────
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${appName}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: [
            { name: 'AZURE_BASE_URL',        value: azureBaseUrl }
            { name: 'AZURE_FLUX_FILL_MODEL', value: azureFluxFillModel }
            { name: 'AZURE_VISION_MODEL',    value: azureVisionModel }
            { name: 'FLUX_IMAGE_SIZE',       value: fluxImageSize }
            { name: 'DEBUG',                 value: 'False' }
            {
              name: 'AZURE_API_KEY'
              secretRef: 'azure-api-key'
            }
            {
              name: 'SECRET_KEY'
              secretRef: 'secret-key'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '10' } }
          }
        ]
      }
    }
  }
  dependsOn: [ acrPull, kvSecretsUser ]
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output appUrl      string = 'https://${app.properties.configuration.ingress.fqdn}'
output acrName     string = acr.name
output acrServer   string = acr.properties.loginServer
output identityId  string = identity.id
output kvName      string = kv.name
