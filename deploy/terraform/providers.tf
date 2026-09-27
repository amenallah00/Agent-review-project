terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }

  # État distant recommandé dès qu'on n'est plus seul sur le projet : évite
  # de perdre le state (et donc la trace de ce qui existe déjà sur Azure) si
  # on change de machine. Décommentez après avoir créé le storage account
  # une première fois (voir README.md de ce dossier).
  #
  # backend "azurerm" {
  #   resource_group_name = "rg-terraform-state"
  #   storage_account_name = "sttfstateaicodereview"
  #   container_name       = "tfstate"
  #   key                  = "agent-review.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      # Permet à `terraform destroy` de vraiment supprimer le Key Vault au
      # lieu de le laisser en "soft-deleted" indéfiniment pendant les tests.
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
  }
}

data "azurerm_client_config" "current" {}
