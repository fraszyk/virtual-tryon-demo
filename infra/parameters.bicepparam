// parameters.bicepparam — fill in your values before first deploy
using './main.bicep'

param environmentName = 'prod'
param containerImage  = 'placeholder/virtual-tryon:latest'   // overridden by CI/CD
param azureBaseUrl    = 'https://<your-resource>.services.ai.azure.com/openai/v1'
param azureApiKey     = '<your-foundry-api-key>'              // stored in Key Vault
