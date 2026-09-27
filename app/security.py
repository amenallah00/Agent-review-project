"""
AAR-13 : Vérification de la signature des webhooks GitHub.

GitHub signe chaque payload de webhook avec HMAC-SHA256, en utilisant le
secret configuré lors de la création de la GitHub App (US 1.1), et l'envoie
dans l'en-tête `X-Hub-Signature-256`. On DOIT vérifier cette signature avant
de faire confiance au contenu du payload, sous peine d'accepter des requêtes
forgées par un tiers.
"""

import hashlib
import hmac

from fastapi import HTTPException, Request


async def verify_signature(request: Request, secret: str) -> bytes:
    """
    Vérifie la signature HMAC-SHA256 du corps de la requête.

    Retourne le corps brut (bytes) si la signature est valide, afin qu'il
    puisse être parsé en JSON par l'appelant. Lève une HTTPException 401
    si l'en-tête est absent ou si la signature ne correspond pas.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not signature_header:
        raise HTTPException(status_code=401, detail="En-tête de signature manquant")

    expected = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # hmac.compare_digest : comparaison en temps constant, pour éviter les
    # attaques par timing sur la comparaison de chaînes.
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Signature invalide")

    return raw_body
