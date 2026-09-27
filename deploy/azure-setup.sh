#!/usr/bin/env bash
# US 4.1 : Provisioning des ressources Azure pour l'agent IA de revue de code.
#
# Reprend exactement les ressources retenues dans le document
# "Ressources et coûts du projet de stage" (v2, choix Azure) :
# Container Apps, Container Registry, Key Vault, Log Analytics/Monitor.
#
# Prérequis : Azure CLI installé et connecté (`az login`).
# Usage : ./deploy/azure-setup.sh
#
# Ce script est idempotent-friendly (utilise `az ... --output none` et des
# noms fixes) : le relancer ne recrée pas de doublons, il met à jour les
# ressources existantes le cas échéant.

set -euo pipefail

# --- Variables à adapter ---
RESOURCE_GROUP="rg-ai-code-review"
LOCATION="eastus"
ACR_NAME="acraicodereview"                 # doit être unique globalement sur Azure
KEY_VAULT_NAME="kv-ai-code-review"         # doit être unique globalement sur Azure
CONTAINERAPPS_ENV="env-ai-code-review"
CONTAINER_APP_NAME="ai-code-review-agent"
LOG_ANALYTICS_NAME="log-ai-code-review"
IMAGE_NAME="ai-code-review-agent"
IMAGE_TAG="latest"

echo "== 1/7 : Groupe de ressources =="
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

echo "== 2/7 : Azure Container Registry (ACR) =="
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

echo "== 3/7 : Build et push de l'image Docker sur ACR =="
# Construit l'image directement sur Azure (pas besoin de Docker en local) :
az acr build \
  --registry "$ACR_NAME" \
  --image "${IMAGE_NAME}:${IMAGE_TAG}" \
  --file Dockerfile \
  .

echo "== 4/7 : Azure Key Vault (secrets) =="
az keyvault create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$KEY_VAULT_NAME" \
  --location "$LOCATION" \
  --output none

echo "   -> Enregistrement des secrets (valeurs vides pour l'instant, à remplir manuellement) :"
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "github-webhook-secret" --value "CHANGEME" --output none
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "github-private-key" --value "CHANGEME" --output none
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "openai-api-key" --value "CHANGEME" --output none
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "anthropic-api-key" --value "CHANGEME" --output none
echo "   ⚠️  Pensez à remplacer ces valeurs CHANGEME (voir étape 8 ci-dessous)."

echo "== 5/7 : Log Analytics (pour Azure Monitor) =="
az monitor log-analytics workspace create \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_NAME" \
  --location "$LOCATION" \
  --output none

LOG_ANALYTICS_CLIENT_ID=$(az monitor log-analytics workspace show \
  --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_NAME" \
  --query customerId -o tsv)
LOG_ANALYTICS_CLIENT_SECRET=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$RESOURCE_GROUP" --workspace-name "$LOG_ANALYTICS_NAME" \
  --query primarySharedKey -o tsv)

echo "== 6/7 : Environnement Container Apps =="
az containerapp env create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$CONTAINERAPPS_ENV" \
  --location "$LOCATION" \
  --logs-workspace-id "$LOG_ANALYTICS_CLIENT_ID" \
  --logs-workspace-key "$LOG_ANALYTICS_CLIENT_SECRET" \
  --output none

echo "== 7/7 : Container App =="
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

az containerapp create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$CONTAINER_APP_NAME" \
  --environment "$CONTAINERAPPS_ENV" \
  --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 3 \
  --cpu 0.5 --memory 1.0Gi \
  --env-vars \
      "GITHUB_APP_ID=CHANGEME" \
      "MAX_PR_LINES=500" \
      "MAX_COMMENTS_PER_REVIEW=15" \
      "LLM_PROVIDER=openai" \
  --output none

echo ""
echo "✅ Provisioning terminé."
echo ""
echo "URL publique de l'agent :"
az containerapp show \
  --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" \
  --query properties.configuration.ingress.fqdn -o tsv

echo ""
echo "⚠️  Étapes manuelles restantes :"
echo "  1. Remplacer les secrets CHANGEME dans Key Vault ($KEY_VAULT_NAME) par vos vraies valeurs :"
echo "     az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-private-key --value @/chemin/vers/cle.pem"
echo "     az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-webhook-secret --value 'votre-secret'"
echo "     az keyvault secret set --vault-name $KEY_VAULT_NAME --name openai-api-key --value 'sk-...'"
echo "  2. Lier ces secrets Key Vault à la Container App (voir deploy/link-keyvault-secrets.sh)."
echo "  3. Mettre à jour l'URL du webhook dans les paramètres de la GitHub App avec l'URL publique ci-dessus + /webhook."
