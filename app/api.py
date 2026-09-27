"""
API REST du tableau de bord, persistée en base (cf. rapport PRLens, annexe E
« Liste complète des points d'accès de l'API REST »). Contrairement aux
anciens endpoints en mémoire de `dashboard.py` (`/api/repos`, `/api/metrics`),
tout ce module lit et écrit dans PostgreSQL/SQLite via SQLAlchemy, et exige
une session utilisateur valide (sauf `/auth/*`).
"""

import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import (
    build_authorize_url,
    create_session_token,
    exchange_code_for_token,
    fetch_github_profile,
    get_current_user,
    require_admin,
    upsert_user,
)
from .config import settings
from .database import get_db
from .db_models import Installation, Review, User

logger = logging.getLogger("codesentinel.api")
router = APIRouter()

# État CSRF du flux OAuth, en mémoire (durée de vie ~ le temps de l'aller-retour
# vers GitHub). Un vrai déploiement multi-instance utiliserait un cache partagé.
_oauth_states: set[str] = set()


def _redirect_uri(request: Request) -> str:
    if settings.github_oauth_redirect_uri:
        return settings.github_oauth_redirect_uri
    return str(request.url_for("oauth_callback"))


# --------------------------------------------------------------------------
# Authentification (cas d'utilisation "S'authentifier", cf. rapport §2.5)
# --------------------------------------------------------------------------

@router.get("/auth/github")
async def oauth_start(request: Request):
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    url = build_authorize_url(_redirect_uri(request), state)
    return RedirectResponse(url)


@router.get("/auth/callback", name="oauth_callback")
async def oauth_callback(request: Request, code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    if not code or state not in _oauth_states:
        # Cf. rapport §2.5, scénario alternatif : code expiré/déjà consommé.
        return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")
    _oauth_states.discard(state)

    try:
        access_token = await exchange_code_for_token(code, _redirect_uri(request))
        profile = await fetch_github_profile(access_token)
    except HTTPException:
        # GitHub momentanément injoignable (503) : on renvoie vers la page
        # d'accueil avec un indicateur d'erreur plutôt qu'un 500 brut — voir
        # Landing.tsx, qui affiche un message et laisse réessayer.
        return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")
    user = upsert_user(db, profile, access_token)
    session_token = create_session_token(user)

    # Pas de cookie inter-domaine (cf. rapport §3.9.1) : le jeton de session
    # est transmis dans le fragment d'URL, lu côté client puis mémorisé.
    return RedirectResponse(f"{settings.frontend_url}/dashboard#token={session_token}")


@router.get("/api/user")
async def get_user(user: User = Depends(get_current_user)):
    return user.to_dict()


# --------------------------------------------------------------------------
# Statistiques et revues (vue "Dashboard", cf. rapport fig. 3.7)
# --------------------------------------------------------------------------

@router.get("/api/stats")
async def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    installations = db.query(Installation).filter(Installation.user_id == user.id).all()
    all_reviews = [r for inst in installations for r in inst.reviews]
    total_reviews = len(all_reviews)
    avg_score = round(sum(r.score for r in all_reviews) / total_reviews) if total_reviews else 0
    total_issues = sum(len(r.comments) for r in all_reviews)
    return {
        "prs_reviewed": total_reviews,
        "average_score": avg_score,
        "issues_caught": total_issues,
        "repos_connected": len(installations),
        "reviews_remaining": max(0, settings.free_tier_review_limit - user.reviews_used) if user.role != "admin" else None,
    }


@router.get("/api/reviews")
async def get_recent_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    installations = db.query(Installation).filter(Installation.user_id == user.id).all()
    all_reviews: list[Review] = sorted(
        (r for inst in installations for r in inst.reviews), key=lambda r: r.reviewed_at, reverse=True
    )
    return {"reviews": [r.to_dict() for r in all_reviews[:20]]}


# --------------------------------------------------------------------------
# Dépôts connectés (cas d'utilisation "Connecter un dépôt", cf. rapport §2.5)
# --------------------------------------------------------------------------

@router.get("/api/repos")
async def list_repos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    installations = db.query(Installation).filter(Installation.user_id == user.id).all()
    recent = sorted((r for inst in installations for r in inst.reviews), key=lambda r: r.reviewed_at, reverse=True)
    return {
        "repos": [inst.to_dict() for inst in installations],
        "recent_reviews": [r.to_dict() for r in recent[:20]],
    }


@router.get("/api/github/repos")
async def list_github_repos(user: User = Depends(get_current_user)):
    """Dépôts GitHub accessibles au compte connecté (cf. rapport §2.5, étape 2 de "Connecter un dépôt")."""
    if not user.github_token:
        raise HTTPException(status_code=400, detail="Aucun jeton GitHub associé à ce compte.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers={"Authorization": f"Bearer {user.github_token}", "Accept": "application/vnd.github+json"},
                params={"per_page": 50, "sort": "updated"},
            )
            resp.raise_for_status()
            repos = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("GitHub injoignable lors de la liste des dépôts de %s : %s", user.handle, exc)
        raise HTTPException(
            status_code=503, detail="GitHub est momentanément injoignable. Réessayez dans un instant."
        ) from exc
    return {
        "repos": [
            {"name": r["full_name"], "private": r["private"], "description": r.get("description")}
            for r in repos
        ]
    }


def _get_installation(db: Session, user: User, name: str) -> Installation:
    inst = db.query(Installation).filter(Installation.user_id == user.id, Installation.repo_name == name).one_or_none()
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Dépôt {name} non connecté.")
    return inst


@router.get("/api/repos/{name:path}/reviews")
async def get_repo_reviews(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = _get_installation(db, user, name)
    reviews = list(inst.reviews)
    breakdown: dict[str, int] = {"security": 0, "quality": 0, "performance": 0, "style": 0, "documentation": 0}
    for r in reviews:
        for c in r.comments:
            breakdown[c.type] = breakdown.get(c.type, 0) + 1
    trend = [r.score for r in reversed(reviews)][-30:]
    return {
        "repo": name,
        "average_score": round(sum(r.score for r in reviews) / len(reviews)) if reviews else 0,
        "trend": trend,
        "issues_breakdown": breakdown,
        "reviews": [r.to_dict() for r in reviews[:30]],
        "settings": inst.to_dict(),
    }


# NB : cette route générique `GET /api/repos/{name:path}` doit rester déclarée
# APRÈS `/api/repos/{name:path}/reviews` — le convertisseur `:path` est
# gourmand (il capture les slashes) et intercepterait sinon toute requête
# GET vers le sous-chemin `/reviews` avant qu'elle n'atteigne la bonne route
# (Starlette résout les routes dans leur ordre de déclaration).
@router.get("/api/repos/{name:path}")
async def get_repo(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_installation(db, user, name).to_dict()


@router.post("/api/repos/{name:path}/enable")
async def enable_repo(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Installation).filter(Installation.user_id == user.id, Installation.repo_name == name).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Le dépôt {name} est déjà connecté.")
    inst = Installation(user_id=user.id, repo_name=name)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst.to_dict()


@router.delete("/api/repos/{name:path}")
async def disable_repo(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = _get_installation(db, user, name)
    db.delete(inst)  # cascade="all, delete-orphan" supprime aussi son historique de revues
    db.commit()
    return {"deleted": name}


class RepoSettingsUpdate(BaseModel):
    min_severity: str | None = None
    languages: list[str] | None = None
    excluded_files: list[str] | None = None
    approve_threshold: int | None = None
    changes_threshold: int | None = None


@router.put("/api/repos/{name:path}/settings")
async def update_repo_settings(name: str, payload: RepoSettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = _get_installation(db, user, name)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inst, field, value)
    db.commit()
    db.refresh(inst)
    return inst.to_dict()


class RepoActiveUpdate(BaseModel):
    active: bool


@router.put("/api/repos/{name:path}/active")
async def update_repo_active(name: str, payload: RepoActiveUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = _get_installation(db, user, name)
    inst.active = payload.active
    db.commit()
    return {"name": name, "active": inst.active}


# --------------------------------------------------------------------------
# Espace d'administration — lecture seule (cf. rapport §3.9.2)
# --------------------------------------------------------------------------

@router.get("/api/admin/stats")
async def admin_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    total_installations = db.query(func.count(Installation.id)).scalar()
    active_installations = db.query(func.count(Installation.id)).filter(Installation.active.is_(True)).scalar()
    total_reviews = db.query(func.count(Review.id)).scalar()
    failed_reviews = db.query(func.count(Review.id)).filter(Review.status == "changes_requested").scalar()
    return {
        "users": total_users,
        "admins": db.query(func.count(User.id)).filter(User.role == "admin").scalar(),
        "repos_connected": total_installations,
        "repos_active": active_installations,
        "reviews_run": total_reviews,
        "failed_reviews": failed_reviews,
    }


@router.get("/api/admin/users")
async def admin_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    out = []
    for u in users:
        out.append({
            **u.to_dict(),
            "repos": len(u.installations),
            "reviews": sum(len(inst.reviews) for inst in u.installations),
        })
    return {"users": out}


@router.get("/api/admin/installations")
async def admin_installations(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    installations = db.query(Installation).all()
    return {
        "installations": [
            {"id": inst.id, **inst.to_dict(), "owner": inst.user.handle if inst.user else None}
            for inst in installations
        ]
    }


@router.get("/api/admin/reviews")
async def admin_reviews(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    reviews = db.query(Review).order_by(Review.reviewed_at.desc()).limit(50).all()
    out = []
    for r in reviews:
        d = r.to_dict()
        d["owner"] = r.installation.user.handle if r.installation and r.installation.user else None
        out.append(d)
    return {"reviews": out}


# --------------------------------------------------------------------------
# Espace d'administration — écriture (CRUD admin complet)
# --------------------------------------------------------------------------

class AdminRoleUpdate(BaseModel):
    role: str  # "user" | "admin"


@router.put("/api/admin/users/{user_id}/role")
async def admin_update_role(user_id: int, payload: AdminRoleUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.role not in ("user", "admin"):
        raise HTTPException(status_code=422, detail="Role must be 'user' or 'admin'.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role.")
    user.role = payload.role
    db.commit()
    return {"id": user.id, "handle": user.handle, "role": user.role}


@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself.")
    db.delete(user)  # cascade supprime installations + reviews + comments
    db.commit()
    return {"deleted": user_id}


@router.put("/api/admin/users/{user_id}/reset-quota")
async def admin_reset_quota(user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.reviews_used = 0
    db.commit()
    return {"id": user.id, "handle": user.handle, "reviews_used": 0}


@router.delete("/api/admin/installations/{installation_id}")
async def admin_delete_installation(installation_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    inst = db.get(Installation, installation_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Installation not found.")
    db.delete(inst)
    db.commit()
    return {"deleted": installation_id}


class AdminActiveUpdate(BaseModel):
    active: bool


@router.put("/api/admin/installations/{installation_id}/active")
async def admin_toggle_installation(installation_id: int, payload: AdminActiveUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    inst = db.get(Installation, installation_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Installation not found.")
    inst.active = payload.active
    db.commit()
    return {"id": inst.id, "repo_name": inst.repo_name, "active": inst.active}