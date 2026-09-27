"""
AAR-12 : Webhook receiver — reçoit et route les événements GitHub
(pull_request.opened/synchronize, issue_comment.created).
"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .auto_approve import should_auto_approve
from .bot_guard import is_bot_sender
from .check_run import determine_conclusion
from .config import settings
from .config_loader import load_repo_config
from .dashboard import router as dashboard_router
from .database import SessionLocal, init_db
from .db_models import Installation, Review, ReviewComment
from .diff_parser import filter_irrelevant_files, parse_diff, total_lines_changed
from .github_app import GitHubClient, get_installation_token
from .label_manager import determine_labels
from .metrics import _categorize, _compute_score, metrics
from .review_engine import review_pull_request
from .review_publisher import publish_review
from .security import verify_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-review")

app = FastAPI(title="CodeSentinel", version="0.1.0")

# --- CORS : nécessaire quand le frontend (Vercel) et le backend (Railway)
# sont sur des domaines différents.
_cors_origins = [settings.frontend_url]
if settings.cors_origins:
    _cors_origins.extend(o.strip() for o in settings.cors_origins.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(api_router)

# --- Frontend React (Vite) : servi en statique en production ---------------
# `npm run build` dans frontend/ génère frontend/dist/. En développement,
# utilisez plutôt `npm run dev` (serveur Vite avec rechargement à chaud,
# proxy vers ce serveur FastAPI — voir frontend/vite.config.ts) : ce bloc ne
# s'active que si un build existe, pour ne pas gêner le workflow de dev.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (_FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    if not settings.session_secret:
        logger.warning(
            "SESSION_SECRET absent : une clé de session aléatoire par processus est utilisée "
            "(cf. rapport §3.9.1). Toutes les sessions seront invalidées au redémarrage."
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_receiver(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
):
    # AAR-13 : la signature est vérifiée AVANT toute lecture du contenu du payload
    raw_body = await verify_signature(request, settings.github_webhook_secret)
    payload = json.loads(raw_body)

    # Bug 3 : anti-boucle — ignorer silencieusement les événements émis par un bot
    if is_bot_sender(payload):
        logger.info("Événement ignoré (émetteur = bot)")
        return {"status": "ignored", "reason": "bot_sender"}

    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            try:
                await handle_pull_request_event(payload)
            except Exception:
                # Défense en profondeur : une erreur inattendue ici ne doit jamais
                # empêcher l'accusé de réception du webhook (GitHub réessaierait
                # sinon en boucle), ni rester invisible dans les logs.
                logger.exception("Erreur inattendue lors du traitement de la PR")
                return {"status": "error", "event": "pull_request", "action": action}
        return {"status": "accepted", "event": "pull_request", "action": action}

    if x_github_event == "issue_comment":
        # US 3.2 : traité dans un ticket ultérieur (gestion des mentions @ai-reviewer)
        logger.info("Événement issue_comment reçu (traitement à venir - US 3.2)")
        return {"status": "accepted", "event": "issue_comment"}

    logger.info("Type d'événement non géré : %s", x_github_event)
    return {"status": "ignored", "reason": "unhandled_event_type"}


async def handle_pull_request_event(payload: dict) -> None:
    """
    Pipeline complet (AAR-12 à AAR-29) : diff -> filtrage (fichiers non
    pertinents + sensibles) -> config par dépôt (AAR-28) -> garde-fou de
    taille (US 4.2) -> revue (linter + patterns + LLM + chunking + filtrage)
    -> validation des lignes (Bug 2) -> publication (commentaires, labels,
    check run, auto-approbation éventuelle) -> métriques (AAR-29).
    """
    installation_id = payload["installation"]["id"]
    repo = payload["repository"]
    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    pr_number = payload["pull_request"]["number"]
    head_sha = payload["pull_request"]["head"]["sha"]

    token = await get_installation_token(installation_id)
    client = GitHubClient(token)

    repo_full_name = f"{owner}/{repo_name}"
    db_installations = _connected_installations(repo_full_name)

    # Un dépôt peut être connecté au tableau de bord par un ou plusieurs
    # comptes (contrainte d'unicité sur (user_id, repo_name), cf. rapport
    # §3.6) — mais tous inactifs (bascule "Active" désactivée, §3.7) doit
    # suspendre la revue sans perdre l'historique déjà accumulé.
    if db_installations and not any(i.active for i in db_installations):
        logger.info("PR #%s ignorée : toutes les installations connectées pour %s sont inactives", pr_number, repo_full_name)
        return

    # US 4.2 bis : limite d'utilisation pour les comptes non-administrateurs
    # (cf. rapport §4.5.2), décomptée par un compteur dédié plutôt qu'un
    # dénombrement des revues existantes.
    over_quota = [
        i for i in db_installations
        if i.active and i.user and i.user.role != "admin" and i.user.reviews_used >= settings.free_tier_review_limit
    ]
    if db_installations and len(over_quota) == len(db_installations):
        logger.info("PR #%s ignorée : quota de revues gratuites atteint pour %s", pr_number, repo_full_name)
        await client.post_issue_comment(
            owner, repo_name, pr_number,
            body=(
                f"⚠️ Le compte connecté à ce dépôt a atteint sa limite de "
                f"{settings.free_tier_review_limit} revues gratuites. Contactez votre administrateur "
                "pour prolonger l'accès."
            ),
        )
        return

    # AAR-28 : charge les surcharges éventuelles de .reviewbot.yml pour ce dépôt
    repo_config = await load_repo_config(client, owner, repo_name, ref=head_sha)

    raw_diff = await client.get_diff(owner, repo_name, pr_number)
    files = parse_diff(raw_diff)
    files = filter_irrelevant_files(files)

    lines_changed = total_lines_changed(files)

    if lines_changed > repo_config.max_pr_lines:
        # US 4.2 : garde-fou de taille (seuil éventuellement surchargé par le dépôt)
        logger.info(
            "PR #%s ignorée : %s lignes modifiées (> %s)",
            pr_number, lines_changed, repo_config.max_pr_lines,
        )
        await client.post_issue_comment(
            owner, repo_name, pr_number,
            body=(
                f"⚠️ Cette Pull Request modifie {lines_changed} lignes, "
                f"au-delà du seuil de {repo_config.max_pr_lines} lignes configuré. "
                "Merci de la scinder en PR plus petites pour permettre une revue automatisée."
            ),
        )
        metrics.record_skipped_too_large()
        return

    logger.info(
        "PR #%s : %s fichier(s) pertinent(s) à analyser, %s lignes changées",
        pr_number, len(files), lines_changed,
    )

    outcome = await review_pull_request(client, owner, repo_name, head_sha, files)

    # AAR-26 : n'auto-approuve que si activé pour ce dépôt et conditions réunies
    auto_approve = repo_config.auto_approve_enabled and should_auto_approve(
        outcome.issues, lines_changed, max_lines=repo_config.auto_approve_max_lines,
    )
    review_event = "APPROVE" if auto_approve else "COMMENT"

    await publish_review(
        client, owner, repo_name, pr_number,
        files=files,
        issues=outcome.issues,
        llm_summaries=outcome.llm_summaries,
        truncated_files=outcome.truncated_files,
        event=review_event,
        cost_skipped_files=outcome.cost_skipped_files,
        flagged_issues_count=outcome.flagged_issues_count,
    )

    # AAR-24 : labels selon la sévérité des problèmes détectés
    labels = determine_labels(outcome.issues)
    await client.add_labels(owner, repo_name, pr_number, labels)
    metrics.record_labels(labels)

    # AAR-25 : check run exploitable comme "required status check"
    conclusion, check_summary = determine_conclusion(outcome.issues)
    await client.create_check_run(owner, repo_name, head_sha, conclusion, check_summary)

    # AAR-29 : métriques cumulées (compteurs en mémoire, indépendants de la base)
    metrics.record_review(
        outcome.issues,
        auto_approved=auto_approve,
        repo=f"{owner}/{repo_name}",
        pr_number=pr_number,
        pr_title=payload["pull_request"].get("title", ""),
        conclusion=conclusion,
    )

    # Persistance en base pour chaque installation connectée au tableau de
    # bord (cf. rapport fig. 3.5) — n'a aucun effet si le dépôt n'est piloté
    # que par le pipeline GitHub Actions, sans compte connecté.
    _persist_review_to_db(db_installations, pr_number, payload["pull_request"].get("title", ""), outcome.issues, conclusion)

    if auto_approve:
        logger.info("PR #%s auto-approuvée (PR mineure, aucun problème bloquant)", pr_number)


def _connected_installations(repo_full_name: str) -> list[Installation]:
    """
    Installations actives ou non pour ce dépôt, tous comptes confondus (cf.
    rapport §3.6). `joinedload(Installation.user)` charge le compte associé
    dans la même requête : les objets restent utilisables après la fermeture
    de la session (accès à `.user` sans requête différée sur une session
    fermée).
    """
    from sqlalchemy.orm import joinedload

    db = SessionLocal()
    try:
        return (
            db.query(Installation)
            .options(joinedload(Installation.user))
            .filter(Installation.repo_name == repo_full_name)
            .all()
        )
    except Exception:  # noqa: BLE001 — la persistance ne doit jamais faire échouer la revue
        logger.exception("Impossible de lire les installations connectées pour %s", repo_full_name)
        return []
    finally:
        db.close()


def _persist_review_to_db(
    installations: list[Installation], pr_number: int, pr_title: str, issues: list, conclusion: str,
) -> None:
    if not installations:
        return
    status = {"success": "approved", "failure": "changes_requested"}.get(conclusion, "commented")
    score = _compute_score(issues)
    db = SessionLocal()
    try:
        for inst_stub in installations:
            if not inst_stub.active:
                continue
            inst = db.get(Installation, inst_stub.id)
            if inst is None:
                continue
            review = Review(installation_id=inst.id, pr_number=pr_number, pr_title=pr_title, score=score, status=status)
            db.add(review)
            db.flush()  # attribue review.id avant d'ajouter les commentaires
            for issue in issues:
                db.add(ReviewComment(
                    review_id=review.id,
                    file_path=issue.filename,
                    line=issue.line,
                    type=_categorize(issue),
                    severity=issue.severity,
                    message=issue.message,
                    suggestion=getattr(issue, "suggestion", None),
                ))
            if inst.user is not None and inst.user.role != "admin":
                inst.user.reviews_used += 1
        db.commit()
    except Exception:  # noqa: BLE001 — la persistance ne doit jamais faire échouer la revue déjà publiée
        logger.exception("Échec de la persistance de la revue en base pour la PR #%s", pr_number)
        db.rollback()
    finally:
        db.close()


# --- SPA fallback : DOIT rester le dernier `@app.get` du fichier -----------
# Toute requête GET qui ne correspond à aucune route ci-dessus (API, auth,
# webhook, health, assets statiques) reçoit `index.html` : c'est ce qui
# permet à React Router de gérer des routes côté client comme `/dashboard`
# ou `/dashboard/repos/acme%2Fapi-gateway` sans un aller-retour serveur par
# route. Si `frontend/dist` n'existe pas encore (build non lancé), on
# répond 404 avec une explication plutôt qu'une erreur muette.
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    from fastapi import HTTPException

    index_file = _FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend non compilé : lancez `npm run build` dans frontend/, ou `npm run dev` pour le développement.",
        )

    # Sert directement les fichiers statiques copiés depuis frontend/public/
    # (favicon.svg, icons.svg, robots.txt, …) avant de retomber sur
    # index.html. Sans ce contrôle, une requête sur /favicon.svg renvoyait
    # la SPA elle-même au lieu du fichier — d'où un favicon qui ne se
    # mettait jamais à jour, peu importe le cache du navigateur.
    candidate = (_FRONTEND_DIST / full_path).resolve()
    try:
        candidate.relative_to(_FRONTEND_DIST.resolve())
    except ValueError:
        candidate = None  # tentative de sortir de dist/ (ex. ../..) : ignorée

    if candidate and candidate.is_file():
        return FileResponse(candidate)

    return FileResponse(index_file)