"""
AAR-11 : Authentification de la GitHub App et client HTTP vers l'API GitHub.

Le flux d'authentification d'une GitHub App se fait en 2 étapes :
1. Générer un JWT signé avec la clé privée de l'App (identité de l'App elle-même).
2. Échanger ce JWT contre un "installation access token" (identité de
   l'installation sur un compte/organisation précis), qui sert ensuite
   pour tous les appels à l'API (lire le diff, poster des commentaires...).
"""

import time
from pathlib import Path

import httpx
import jwt

from .config import settings
from .rate_limit import request_with_retry

GITHUB_API = "https://api.github.com"


def _load_private_key() -> str:
    """
    En local (dev) : lit le fichier .pem indiqué par GITHUB_PRIVATE_KEY_PATH.
    En production (Azure) : si GITHUB_PRIVATE_KEY (contenu PEM complet) est
    fourni comme secret d'environnement, il est utilisé directement — pas
    besoin de monter un fichier dans le conteneur (voir azure-setup.sh).
    """
    if settings.github_private_key:
        return settings.github_private_key
    return Path(settings.github_private_key_path).read_text()


def generate_app_jwt() -> str:
    """
    Génère un JWT signé RS256, valide 10 minutes (maximum autorisé par
    GitHub), utilisé pour s'authentifier en tant que GitHub App.
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,  # marge de sécurité pour la désynchronisation d'horloge
        "exp": now + (10 * 60),
        "iss": settings.github_app_id,
    }
    private_key = _load_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """
    Échange le JWT de l'App contre un token d'accès à court terme
    (1h de validité) pour une installation précise (US 1.1).
    """
    app_jwt = generate_app_jwt()
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["token"]


class GitHubClient:
    """Client HTTP authentifié pour une installation GitHub App donnée."""

    def __init__(self, installation_token: str):
        self._headers = {
            "Authorization": f"Bearer {installation_token}",
            "Accept": "application/vnd.github+json",
        }

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Récupère le diff brut au format unified diff (US 2.1)."""
        headers = {**self._headers, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.text

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Récupère le contenu complet d'un fichier à une référence (SHA/branche)
        donnée — nécessaire pour le linter (AAR-15), qui a besoin du fichier
        entier et pas seulement du diff pour analyser une syntaxe valide.
        """
        import base64

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
                headers=self._headers,
                params={"ref": ref},
            )
            resp.raise_for_status()
            data = resp.json()
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    async def create_review(
        self, owner: str, repo: str, pr_number: int, comments: list[dict],
        body: str = "", event: str = "COMMENT",
    ) -> dict:
        """
        Poste une revue avec des commentaires attachés aux lignes (US 3.1).
        `event` : "COMMENT" (défaut) | "APPROVE" (AAR-26) | "REQUEST_CHANGES".
        """
        payload = {"body": body, "event": event, "comments": comments}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await request_with_retry(
                client, "POST",
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                headers=self._headers, json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def post_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        """
        Poste un commentaire simple sur le fil de discussion de la PR
        (utilisé pour les réponses aux mentions, US 3.2, et les messages
        d'avertissement type "PR trop volumineuse", US 4.2).
        """
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await request_with_retry(
                client, "POST",
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                headers=self._headers, json={"body": body},
            )
            resp.raise_for_status()
            return resp.json()

    async def add_labels(self, owner: str, repo: str, issue_number: int, labels: list[str]) -> dict:
        """AAR-24 : ajoute des labels sur la PR (les PR sont des issues côté API GitHub)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await request_with_retry(
                client, "POST",
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/labels",
                headers=self._headers, json={"labels": labels},
            )
            resp.raise_for_status()
            return resp.json()

    async def create_check_run(
        self, owner: str, repo: str, head_sha: str, conclusion: str, summary: str,
    ) -> dict:
        """
        AAR-25 : publie un Check Run terminé sur le commit de tête de la PR.
        Nécessite la permission "checks: write" sur la GitHub App (voir README).
        """
        from .check_run import CHECK_NAME

        payload = {
            "name": CHECK_NAME,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": CHECK_NAME, "summary": summary},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await request_with_retry(
                client, "POST",
                f"{GITHUB_API}/repos/{owner}/{repo}/check-runs",
                headers=self._headers, json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def approve_pull_request(self, owner: str, repo: str, pr_number: int, body: str = "") -> dict:
        """
        AAR-26 : approuve la PR (event=APPROVE). N'effectue JAMAIS de merge —
        seule une approbation est soumise, la fusion reste une action distincte
        et humaine (ou soumise aux règles de branch protection du dépôt).
        """
        return await self.create_review(owner, repo, pr_number, comments=[], body=body, event="APPROVE")
