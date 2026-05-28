# setup.ps1 — One-time Azure setup for Virtual Try-On
# Run ONCE before the first deployment. Requires: az CLI, gh CLI, logged-in to both.
#
# Usage:
#   .\infra\setup.ps1 -ResourceGroup "rg-virtual-tryon" -Location "swedencentral"

param(
    [Parameter(Mandatory)][string]$ResourceGroup,
    [string]$Location = "swedencentral",
    [string]$AppName  = "virtual-tryon"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Virtual Try-On — Azure one-time setup ===" -ForegroundColor Cyan

# ── 1. Resource Group ─────────────────────────────────────────────────────────
Write-Host "`n[1/6] Creating resource group '$ResourceGroup'..."
az group create --name $ResourceGroup --location $Location | Out-Null

# ── 2. Register providers ─────────────────────────────────────────────────────
Write-Host "[2/6] Registering Azure providers..."
foreach ($ns in @("Microsoft.App", "Microsoft.ContainerRegistry", "Microsoft.KeyVault", "Microsoft.OperationalInsights")) {
    az provider register --namespace $ns | Out-Null
}

# ── 3. Deploy Bicep (initial — with placeholder image) ───────────────────────
Write-Host "[3/6] Deploying infrastructure (Bicep)..."
$azureBaseUrl = Read-Host "  Azure AI Foundry base URL (e.g. https://<resource>.services.ai.azure.com/openai/v1)"
$azureApiKey  = Read-Host "  Azure AI Foundry API key" -AsSecureString
$apiKeyPlain  = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($azureApiKey))

$output = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file "$PSScriptRoot\main.bicep" `
    --parameters environmentName=prod `
                 containerImage="mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" `
                 azureBaseUrl="$azureBaseUrl" `
                 azureApiKey="$apiKeyPlain" `
    --query "properties.outputs" -o json | ConvertFrom-Json

$acrName   = $output.acrName.value
$acrServer = $output.acrServer.value
$appUrl    = $output.appUrl.value

Write-Host "  ACR:    $acrServer"
Write-Host "  App URL: $appUrl"

# ── 4. Service Principal + OIDC for GitHub Actions ───────────────────────────
Write-Host "[4/6] Creating service principal for GitHub Actions..."
$subscriptionId = az account show --query id -o tsv
$tenantId       = az account show --query tenantId -o tsv

$sp = az ad sp create-for-rbac `
    --name "sp-$AppName-github" `
    --role Contributor `
    --scopes "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup" `
    --query "{clientId:appId, tenantId:tenant}" -o json | ConvertFrom-Json

$clientId = $sp.clientId

# Additional role: AcrPush on ACR
$acrId = az acr show --name $acrName --resource-group $ResourceGroup --query id -o tsv
az role assignment create --assignee $clientId --role AcrPush --scope $acrId | Out-Null

# OIDC federated credential for GitHub Actions
$repoInfo = gh repo view --json nameWithOwner -q .nameWithOwner
Write-Host "  GitHub repo: $repoInfo"

$fedCred = @{
    name        = "github-actions-main"
    issuer      = "https://token.actions.githubusercontent.com"
    subject     = "repo:${repoInfo}:ref:refs/heads/main"
    audiences   = @("api://AzureADTokenExchange")
    description = "GitHub Actions OIDC for main branch"
} | ConvertTo-Json -Compress

$spObjectId = az ad sp show --id $clientId --query id -o tsv
az ad app federated-credential create --id $spObjectId --parameters $fedCred | Out-Null

# ── 5. GitHub secrets ─────────────────────────────────────────────────────────
Write-Host "[5/6] Setting GitHub Actions secrets..."
gh secret set AZURE_CLIENT_ID       --body $clientId
gh secret set AZURE_TENANT_ID       --body $tenantId
gh secret set AZURE_SUBSCRIPTION_ID --body $subscriptionId
gh secret set AZURE_RESOURCE_GROUP  --body $ResourceGroup
gh secret set ACR_NAME              --body $acrName

# ── 6. Done ───────────────────────────────────────────────────────────────────
Write-Host "`n=== Setup complete! ===" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Push any commit to main → GitHub Actions will build & deploy automatically"
Write-Host "  2. App URL: $appUrl"
Write-Host "  3. Monitor: https://portal.azure.com → Resource Group '$ResourceGroup'"
