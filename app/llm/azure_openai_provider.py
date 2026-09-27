"""
Implémentation Azure OpenAI Service de LLMProvider — alternative à l'appel
direct de l'API OpenAI, utile si vous disposez déjà d'un abonnement Azure
(via votre organisation) et préférez éviter la facturation personnelle
directe. Utilise le même modèle GPT-4o, juste hébergé sur l'infrastructure
Azure — reste conforme au cahier des charges ("API OpenAI (GPT-4o)").

Différences avec l'API OpenAI directe (app/llm/openai_provider.py) :
- L'URL inclut le nom de la ressource Azure et le nom du "deployment"
  (pas juste le nom du modèle).
- L'authentification se fait via l'en-tête `api-key`, pas `Authorization: Bearer`.
- Le corps de la requête n'inclut PAS le champ "model" : c'est le déploiement
  visé dans l'URL qui détermine le modèle utilisé.
"""

import httpx

from .base import LLMProvider, ReviewResult, parse_review_json

DEFAULT_API_VERSION = "2024-08-01-preview"


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str = DEFAULT_API_VERSION):
        if not endpoint or not deployment:
            raise ValueError(
                "AzureOpenAIProvider nécessite AZURE_OPENAI_ENDPOINT et AZURE_OPENAI_DEPLOYMENT (voir .env.example)"
            )
        self._url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={api_version}"
        )
        self._api_key = api_key

    async def analyze(self, system_prompt: str, user_prompt: str) -> ReviewResult:
        headers = {"api-key": self._api_key, "Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self._url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Azure OpenAI API error {resp.status_code}: {resp.text}")
            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        return parse_review_json(raw_content)
