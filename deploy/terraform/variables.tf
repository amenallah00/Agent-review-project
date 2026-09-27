variable "resource_group_name" {
  description = "Nom du groupe de ressources Azure"
  type        = string
  default     = "rg-ai-code-review"
}

variable "location" {
  description = "Région Azure"
  type        = string
  default     = "eastus"
}

variable "acr_name" {
  description = "Nom de l'Azure Container Registry (doit être unique globalement sur Azure, alphanumérique uniquement)"
  type        = string
  default     = "acraicodereview"
}

variable "key_vault_name" {
  description = "Nom du Key Vault (doit être unique globalement sur Azure)"
  type        = string
  default     = "kv-ai-code-review"
}

variable "log_analytics_name" {
  description = "Nom du workspace Log Analytics"
  type        = string
  default     = "log-ai-code-review"
}

variable "container_app_env_name" {
  description = "Nom de l'environnement Container Apps"
  type        = string
  default     = "env-ai-code-review"
}

variable "container_app_name" {
  description = "Nom de la Container App"
  type        = string
  default     = "ai-code-review-agent"
}

variable "image_name" {
  description = "Nom de l'image Docker (sans registre ni tag)"
  type        = string
  default     = "ai-code-review-agent"
}

variable "image_tag" {
  description = "Tag de l'image Docker à déployer"
  type        = string
  default     = "latest"
}

# --- Secrets applicatifs ---
# Fournis via terraform.tfvars (jamais committé, voir .gitignore) ou via
# TF_VAR_xxx en variables d'environnement — jamais en dur dans ce fichier.

variable "github_app_id" {
  description = "App ID de la GitHub App"
  type        = string
}

variable "github_webhook_secret" {
  description = "Secret du webhook GitHub (openssl rand -hex 32)"
  type        = string
  sensitive   = true
}

variable "github_private_key_pem" {
  description = "Contenu complet de la clé privée .pem de la GitHub App"
  type        = string
  sensitive   = true
}

variable "llm_provider" {
  description = "Fournisseur LLM : openai | anthropic | azure_openai"
  type        = string
  default     = "openai"
}

variable "openai_api_key" {
  description = "Clé API OpenAI (vide si llm_provider != openai)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Clé API Anthropic (vide si llm_provider != anthropic)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "max_pr_lines" {
  description = "US 4.2 : seuil de lignes au-delà duquel une PR est ignorée"
  type        = number
  default     = 500
}

variable "max_comments_per_review" {
  type    = number
  default = 15
}
