"""
Configuration centralisée de l'application, chargée depuis les variables
d'environnement (voir .env.example). Ticket : Configurer environnement dev.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- GitHub App (US 1.1) ---
    github_app_id: str
    github_private_key_path: str = "./secrets/github-app-private-key.pem"
    github_private_key: str | None = None  # contenu PEM direct (déploiement Azure, cf. azure-setup.sh)
    github_webhook_secret: str

    # --- Fournisseur LLM (section 3 du cahier des charges) ---
    llm_provider: str = "openai"  # "openai" | "anthropic" | "azure_openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # --- Azure OpenAI Service (alternative à l'appel direct OpenAI, ex: si
    # votre organisation dispose déjà d'un abonnement Azure) ---
    azure_openai_endpoint: str | None = None      # ex: https://amenallahbenabdrabah.openai.azure.com
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None     # nom donné au déploiement dans Azure AI Foundry
    azure_openai_api_version: str = "2024-08-01-preview"

    # --- Garde-fous de coûts (US 4.2) ---
    max_pr_lines: int = 500

    # --- Garde-fou anti rate-limit GitHub (AAR-32 [RISQUE]) ---
    max_comments_per_review: int = 15

    # --- Garde-fou anti-hallucination LLM (AAR-33 [RISQUE]) ---
    min_issue_confidence: str = "medium"  # "low" | "medium" | "high"

    # --- Garde-fou de coûts sur les gros diffs multi-fichiers (AAR-34 [RISQUE]) ---
    max_chunks_per_review: int = 8

    # --- Tableau de bord : base de données, session, OAuth (cf. rapport PRLens §3.6/3.9) ---
    database_url: str = "sqlite:///./codesentinel.db"
    session_secret: str | None = None
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_redirect_uri: str | None = None  # défaut : <host>/auth/callback
    frontend_url: str = "http://localhost:8000"
    cors_origins: str = ""  # comma-separated extra origins, e.g. "https://my-app.vercel.app,https://other.com"
    free_tier_review_limit: int = 50

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
