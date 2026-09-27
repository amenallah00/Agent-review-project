# =============================================================================
# 1. Groupe de ressources
# =============================================================================
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

# =============================================================================
# 2. Azure Container Registry
# =============================================================================
resource "azurerm_container_registry" "main" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}

# NB : Terraform ne construit pas d'image Docker (ce n'est pas son rôle —
# il gère l'infra, pas le build applicatif). Le build/push reste fait par
# `az acr build` (voir deploy/build-and-push.sh) ou par le pipeline CI/CD
# .github/workflows/deploy.yml, exécuté séparément avant `terraform apply`
# si l'image doit changer.

# =============================================================================
# 3. Key Vault + secrets
# =============================================================================
resource "azurerm_key_vault" "main" {
  name                = var.key_vault_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
}

resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

resource "azurerm_key_vault_secret" "github_webhook_secret" {
  name         = "github-webhook-secret"
  value        = var.github_webhook_secret
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "github_private_key" {
  name         = "github-private-key"
  value        = var.github_private_key_pem
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key != "" ? var.openai_api_key : "CHANGEME"
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "anthropic-api-key"
  value        = var.anthropic_api_key != "" ? var.anthropic_api_key : "CHANGEME"
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_key_vault_access_policy.terraform]
}

# =============================================================================
# 4. Log Analytics (pour Azure Monitor / logs de la Container App)
# =============================================================================
resource "azurerm_log_analytics_workspace" "main" {
  name                = var.log_analytics_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# =============================================================================
# 5. Environnement Container Apps
# =============================================================================
resource "azurerm_container_app_environment" "main" {
  name                       = var.container_app_env_name
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

# =============================================================================
# 6. Identité managée : permet à la Container App de lire le Key Vault sans
#    stocker le login/mot de passe ACR ou les secrets en dur dans le state.
# =============================================================================
resource "azurerm_user_assigned_identity" "container_app" {
  name                = "id-ai-code-review-agent"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_key_vault_access_policy" "container_app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.container_app.principal_id

  secret_permissions = ["Get", "List"]
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_app.principal_id
}

# =============================================================================
# 7. Container App
# =============================================================================
resource "azurerm_container_app" "main" {
  name                         = var.container_app_name
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.container_app.id
  }

  secret {
    name                = "github-webhook-secret"
    key_vault_secret_id = azurerm_key_vault_secret.github_webhook_secret.id
    identity            = azurerm_user_assigned_identity.container_app.id
  }
  secret {
    name                = "github-private-key"
    key_vault_secret_id = azurerm_key_vault_secret.github_private_key.id
    identity            = azurerm_user_assigned_identity.container_app.id
  }
  secret {
    name                = "openai-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.openai_api_key.id
    identity            = azurerm_user_assigned_identity.container_app.id
  }
  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.anthropic_api_key.id
    identity            = azurerm_user_assigned_identity.container_app.id
  }

  template {
    min_replicas = 0
    max_replicas = 3

    container {
      name   = "agent-review"
      image  = "${azurerm_container_registry.main.login_server}/${var.image_name}:${var.image_tag}"
      cpu    = 0.5
      memory = "1.0Gi"

      env {
        name  = "GITHUB_APP_ID"
        value = var.github_app_id
      }
      env {
        name  = "MAX_PR_LINES"
        value = tostring(var.max_pr_lines)
      }
      env {
        name  = "MAX_COMMENTS_PER_REVIEW"
        value = tostring(var.max_comments_per_review)
      }
      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }
      env {
        name        = "GITHUB_WEBHOOK_SECRET"
        secret_name = "github-webhook-secret"
      }
      env {
        name        = "GITHUB_PRIVATE_KEY"
        secret_name = "github-private-key"
      }
      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # L'image est poussée séparément (az acr build / CI), donc on ignore les
  # changements de tag faits hors Terraform pour éviter un `plan` qui
  # voudrait "revenir" à l'ancienne image à chaque apply.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}
