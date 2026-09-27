"""AAR-18 : Implémentation OpenAI (GPT-4o) de LLMProvider."""

import httpx

from .base import LLMProvider, ReviewResult, parse_review_json

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    async def analyze(self, system_prompt: str, user_prompt: str) -> ReviewResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text}")
            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        return parse_review_json(raw_content)
