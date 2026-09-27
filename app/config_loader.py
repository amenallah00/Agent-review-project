"""
AAR-28 : Configuration par dépôt via un fichier `.reviewbot.yml` à la
racine du dépôt cible, permettant de surcharger les seuils globaux
(app/config.py) pour un dépôt précis, sans redéployer l'agent.

Exemple de `.reviewbot.yml` :
    max_pr_lines: 800
    max_comments_per_review: 10
    auto_approve_enabled: false
    ignored_paths:
      - "generated/"
      - "*.snap"
"""

import logging

import yaml

from .config import settings

logger = logging.getLogger("agent-review.config_loader")

CONFIG_FILENAME = ".reviewbot.yml"


class RepoConfig:
    """Configuration effective pour un dépôt (défauts globaux + surcharges)."""

    def __init__(
        self,
        max_pr_lines: int,
        max_comments_per_review: int,
        llm_provider: str,
        auto_approve_enabled: bool = True,
        auto_approve_max_lines: int = 30,
        ignored_paths: list[str] | None = None,
    ):
        self.max_pr_lines = max_pr_lines
        self.max_comments_per_review = max_comments_per_review
        self.llm_provider = llm_provider
        self.auto_approve_enabled = auto_approve_enabled
        self.auto_approve_max_lines = auto_approve_max_lines
        self.ignored_paths = ignored_paths or []

    def to_dict(self) -> dict:
        return {
            "max_pr_lines": self.max_pr_lines,
            "max_comments_per_review": self.max_comments_per_review,
            "llm_provider": self.llm_provider,
            "auto_approve_enabled": self.auto_approve_enabled,
            "auto_approve_max_lines": self.auto_approve_max_lines,
            "ignored_paths": self.ignored_paths,
        }


def default_config() -> RepoConfig:
    """Configuration effective quand aucun `.reviewbot.yml` n'est présent (ou invalide)."""
    return RepoConfig(
        max_pr_lines=settings.max_pr_lines,
        max_comments_per_review=settings.max_comments_per_review,
        llm_provider=settings.llm_provider,
    )


def parse_repo_config(yaml_content: str) -> RepoConfig:
    """
    Parse `.reviewbot.yml` et le fusionne avec les valeurs par défaut
    globales — seules les clés reconnues et présentes dans le fichier
    surchargent la config globale ; le reste est ignoré silencieusement
    plutôt que de faire échouer le pipeline pour une faute de frappe.
    """
    base = default_config().to_dict()

    try:
        overrides = yaml.safe_load(yaml_content) or {}
    except yaml.YAMLError:
        logger.warning("`.reviewbot.yml` invalide (YAML malformé), utilisation des valeurs par défaut")
        overrides = {}

    if not isinstance(overrides, dict):
        overrides = {}

    merged = {**base, **{k: v for k, v in overrides.items() if k in base}}
    return RepoConfig(**merged)


async def load_repo_config(client, owner: str, repo: str, ref: str) -> RepoConfig:
    """
    Tente de récupérer `.reviewbot.yml` à la racine du dépôt ; si absent
    (cas normal pour la plupart des dépôts) ou invalide, retourne la
    configuration par défaut sans jamais faire échouer le pipeline.
    """
    try:
        content = await client.get_file_content(owner, repo, CONFIG_FILENAME, ref=ref)
    except Exception:
        return default_config()
    return parse_repo_config(content)
