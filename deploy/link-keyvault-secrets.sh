#!/usr/bin/env bash
# Lie les secrets Azure Key Vault à la Container App via une identité
# managée (recommandé par Microsoft plutôt que de passer les secrets en
# clair dans --env-vars). À exécuter APRÈS azure-setup.sh, une fois les
# vraies valeurs de secrets renseignées dans le Key Vault.

set -euo pipefail

RESOURCE_GROUP="rg-ai-code-review"
KEY_VAULT_NAME="kv-ai-code-review"
CONTAINER_APP_NAME="ai-code-review-agent"

echo "== 1/3 : Activation de l'identité managée sur la Container App =="
az containerapp identity assign \
  --resource-group "$RESOURCE_GROUP" \
  --name "$CONTAINER_APP_NAME" \
  --system-assigned \
  --output none

PRINCIPAL_ID=$(az containerapp identity show \
  --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" \
  --query principalId -o tsv)

echo "== 2/3 : Autorisation de lecture des secrets sur le Key Vault =="
az keyvault set-policy \
  --name "$KEY_VAULT_NAME" \
  --object-id "$PRINCIPAL_ID" \
  --secret-permissions get list \
  --output none

echo "== 3/3 : Référencement des secrets Key Vault comme variables d'environnement sécurisées =="
KEY_VAULT_URI=$(az keyvault show --name "$KEY_VAULT_NAME" --query properties.vaultUri -o tsv)

az containerapp secret set \
  --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" \
  --secrets \
    "github-webhook-secret=keyvaultref:${KEY_VAULT_URI}secrets/github-webhook-secret,identityref:system" \
    "github-private-key=keyvaultref:${KEY_VAULT_URI}secrets/github-private-key,identityref:system" \
    "openai-api-key=keyvaultref:${KEY_VAULT_URI}secrets/openai-api-key,identityref:system" \
    "anthropic-api-key=keyvaultref:${KEY_VAULT_URI}secrets/anthropic-api-key,identityref:system" \
  --output none

az containerapp update \
  --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_NAME" \
  --set-env-vars \
    "GITHUB_WEBHOOK_SECRET=secretref:github-webhook-secret" \
    "GITHUB_PRIVATE_KEY=secretref:github-private-key" \
    "OPENAI_API_KEY=secretref:openai-api-key" \
    "ANTHROPIC_API_KEY=secretref:anthropic-api-key" \
  --output none

echo "✅ Secrets liés. La Container App va redémarrer avec les nouvelles variables."
