"""
AAR-32 [RISQUE] Rate limiting GitHub API — Trop de commentaires.

Deux mécanismes de mitigation, complémentaires :
1. `comment_filter.filter_and_prioritize` (AAR-20) plafonne déjà le NOMBRE
   de commentaires envoyés dans une seule revue — ça réduit la taille de la
   requête, mais ne protège pas contre les limites de débit de l'API elle-même
   (ex: plusieurs PR traitées en parallèle, ou limite secondaire GitHub sur
   les créations rapprochées de commentaires).
2. Ce module : retry avec backoff sur les réponses HTTP 429 (rate limit
   classique) et 403 avec "secondary rate limit" (limite anti-abus de GitHub,
   qui peut se déclencher même sans avoir épuisé le quota horaire normal).
"""

import asyncio
import logging

import httpx

logger = logging.getLogger("agent-review.rate_limit")


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict,
    json: dict | None = None,
    max_retries: int = 3,
) -> httpx.Response:
    """
    Exécute une requête HTTP en gérant les limites de taux de GitHub :
    - 429 : rate limit classique.
    - 403 avec le corps mentionnant "secondary rate limit" : limite anti-abus
      (ex: trop de créations de commentaires en peu de temps).
    Respecte l'en-tête `Retry-After` si GitHub le fournit, sinon backoff
    exponentiel (1s, 2s, 4s...).
    """
    last_response: httpx.Response | None = None

    for attempt in range(max_retries + 1):
        response = await client.request(method, url, headers=headers, json=json)
        last_response = response

        if not _is_rate_limited(response):
            return response

        if attempt >= max_retries:
            logger.warning(
                "Rate limit GitHub persistant après %d tentatives sur %s %s",
                max_retries, method, url,
            )
            return response

        wait_seconds = _compute_wait_seconds(response, attempt)
        logger.info(
            "Rate limit GitHub détecté (status=%s) sur %s %s — nouvelle tentative dans %.1fs",
            response.status_code, method, url, wait_seconds,
        )
        await asyncio.sleep(wait_seconds)

    return last_response  # pragma: no cover (inatteignable, boucle couvre déjà tous les cas)


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code == 403:
        if response.headers.get("x-ratelimit-remaining") == "0":
            return True
        if "secondary rate limit" in response.text.lower() or "abuse" in response.text.lower():
            return True
    return False


def _compute_wait_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(2 ** attempt)  # 1s, 2s, 4s, ...
