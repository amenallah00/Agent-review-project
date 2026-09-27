"""AAR-18 : Implémentation Anthropic (Claude 3.5 Sonnet) de LLMProvider."""

import httpx

from .base import LLMProvider, ReviewResult, parse_review_json

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-5"):
        self._api_key = api_key
        self._model = model

    async def analyze(self, system_prompt: str, user_prompt: str) -> ReviewResult:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            if resp.status_code >= 400:
                # httpx.raise_for_status() ne montre que le code HTTP ; le corps de la
                # réponse contient le vrai motif (modèle invalide, clé API, quota...),
                # indispensable pour diagnostiquer une erreur 400/401/429 en production.
                raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text}")
            data = resp.json()

        raw_content = data["content"][0]["text"]
        return parse_review_json(raw_content)
