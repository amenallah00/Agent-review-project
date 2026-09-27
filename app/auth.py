"""
Authentification du tableau de bord (cf. rapport PRLens, cas d'utilisation
« S'authentifier », §2.5, et §3.9 « Session sans cookie inter-domaine »).

Flux : OAuth 2.0 GitHub -> échange du code contre un jeton d'accès GitHub
-> upsert de l'utilisateur en base -> émission d'un jeton de session (JWT)
transmis en en-tête `Authorization: Bearer`, jamais en cookie.
"""

import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .db_models import User

logger = logging.getLogger("codesentinel.auth")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 jours (cf. rapport §3.9.2)


def _session_secret() -> str:
    if settings.session_secret:
        return settings.session_secret
    # Cf. rapport §3.9.1 : en l'absence de SESSION_SECRET, une clé aléatoire
    # par processus est utilisée (avertissement au démarrage, voir main.py).
    global _RUNTIME_SECRET
    try:
        return _RUNTIME_SECRET
    except NameError:
        _RUNTIME_SECRET = secrets.token_hex(32)
        return _RUNTIME_SECRET


def build_authorize_url(redirect_uri: str, state: str) -> str:
    if not settings.github_oauth_client_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "OAuth GitHub non configuré : renseignez GITHUB_OAUTH_CLIENT_ID / "
                "GITHUB_OAUTH_CLIENT_SECRET dans .env (voir .env.example)."
            ),
        )
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user repo",
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, redirect_uri: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_oauth_client_id,
                    "client_secret": settings.github_oauth_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("GitHub OAuth injoignable lors de l'échange du code : %s", exc)
        raise HTTPException(status_code=503, detail="GitHub est momentanément injoignable. Réessayez.") from exc
    if "access_token" not in data:
        logger.warning("Échec de l'échange OAuth GitHub : %s", data)
        raise HTTPException(status_code=401, detail="Échec de l'authentification GitHub (code expiré ou invalide).")
    return data["access_token"]


async def fetch_github_profile(access_token: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                GITHUB_USER_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("GitHub injoignable lors de la récupération du profil : %s", exc)
        raise HTTPException(status_code=503, detail="GitHub est momentanément injoignable. Réessayez.") from exc


def upsert_user(db: Session, profile: dict, access_token: str) -> User:
    """
    L'identifiant numérique GitHub sert de clé d'identité, jamais le
    pseudonyme (cf. rapport §4.4.2 : un pseudonyme peut être réattribué).
    """
    github_id = profile["id"]
    user = db.query(User).filter(User.github_id == github_id).one_or_none()
    if user is None:
        user = User(
            github_id=github_id,
            handle=profile.get("login", str(github_id)),
            name=profile.get("name"),
            avatar_url=profile.get("avatar_url"),
            role="user",
            github_token=access_token,
        )
        db.add(user)
    else:
        user.handle = profile.get("login", user.handle)
        user.name = profile.get("name")
        user.avatar_url = profile.get("avatar_url")
        user.github_token = access_token
    db.commit()
    db.refresh(user)
    return user


def create_session_token(user: User) -> str:
    now = int(time.time())
    # PyJWT >= 2.10 impose que "sub" (RFC 7519) soit une chaîne ; l'identifiant
    # est reconverti en entier côté decode (get_current_user ci-dessous).
    payload = {"sub": str(user.id), "iat": now, "exp": now + SESSION_TTL_SECONDS}
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def _decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée.") from exc


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentification requise.")
    payload = _decode_session_token(header.removeprefix("Bearer ").strip())
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Session invalide.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    # Le rôle est relu en base à chaque requête (get_current_user ci-dessus
    # recharge l'utilisateur) : une révocation de rôle prend effet
    # immédiatement, sans attendre l'expiration du jeton (cf. rapport §3.9.2).
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs.")
    return user