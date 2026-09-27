"""
Endpoints de diagnostic sans état, indépendants de la persistance (§3.6) et
de l'authentification (§3.9) : consultés par le tableau de bord React
(frontend/), servi séparément par app/main.py (build statique en production,
serveur Vite avec proxy en développement — voir frontend/vite.config.ts).

- `/api/config` : configuration globale par défaut (avant surcharge
  éventuelle par un `.reviewbot.yml` par dépôt).
- `/api/metrics` : compteurs cumulés en mémoire (AAR-29), remis à zéro à
  chaque redémarrage du serveur — distincts de l'historique persisté en
  base (voir app/api.py, alimenté par app/db_models.py).
- `/api/test-review` : exécute le VRAI pipeline (linter + patterns + LLM
  configuré dans `.env` + filtrage + labels + check + auto-approve) sur un
  extrait de code collé par l'utilisateur, sans passer par GitHub — outil
  de diagnostic sans authentification ni persistance.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from .auto_approve import should_auto_approve
from .check_run import determine_conclusion
from .comment_filter import filter_and_prioritize
from .config import settings
from .config_loader import default_config
from .diff_parser import FileChange, Hunk
from .hallucination_guard import filter_hallucinations
from .label_manager import determine_labels
from .linter import lint_file
from .local_findings import lint_issues_to_review_issues, pattern_matches_to_review_issues
from .metrics import metrics
from .pattern_detector import detect_patterns
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt
from .review_engine import get_llm_provider

logger = logging.getLogger("agent-review.dashboard")

router = APIRouter()


@router.get("/api/config")
async def get_config():
    """Configuration globale par défaut (avant surcharge éventuelle par un `.reviewbot.yml`)."""
    return default_config().to_dict()


@router.get("/api/metrics")
async def get_metrics():
    return metrics.to_dict()


class TestReviewRequest(BaseModel):
    filename: str = "test.py"
    code: str


@router.post("/api/test-review")
async def test_review(payload: TestReviewRequest):
    """
    Exécute le pipeline de revue complet (hors publication GitHub, puisqu'il
    n'y a pas de vraie PR ici) sur le code collé par l'utilisateur — traite
    tout le code comme s'il s'agissait de lignes ajoutées dans un diff.

    Appelle réellement l'API OpenAI/Anthropic configurée dans `.env` : les
    erreurs (clé API absente/invalide, quota dépassé...) sont renvoyées
    dans le champ `error` plutôt que de faire planter la requête, pour
    rester utilisable comme outil de diagnostic.
    """
    lines = payload.code.splitlines() or [""]
    hunk_content = "\n".join(f"+{line}" for line in lines)
    hunk = Hunk(header=f"@@ -0,0 +1,{len(lines)} @@", new_start=1, content=hunk_content)
    file_change = FileChange(filename=payload.filename, hunks=[hunk], lines_added=len(lines))

    added_lines = file_change.added_lines_with_content()

    lint_issues = lint_file(payload.filename, payload.code)
    pattern_matches = detect_patterns(payload.filename, added_lines)

    # Comme dans review_engine.py : les découvertes locales déterministes
    # (linter + patterns) alimentent TOUJOURS le résultat, indépendamment du
    # succès de l'appel LLM ci-dessous — cohérence avec le pipeline réel.
    all_issues = lint_issues_to_review_issues(lint_issues) + pattern_matches_to_review_issues(pattern_matches)

    result_summary = ""
    final_issues = []
    flagged_count = 0
    error = None

    try:
        llm = get_llm_provider()
        user_prompt = build_user_prompt([file_change], lint_issues, pattern_matches)
        result = await llm.analyze(SYSTEM_PROMPT, user_prompt)
        result_summary = result.summary
        all_issues.extend(result.issues)
    except Exception as exc:  # noqa: BLE001 — outil de diagnostic, on veut toujours une réponse exploitable
        logger.exception("Échec de l'appel LLM dans le testeur du dashboard")
        error = f"{type(exc).__name__}: {exc}"

    # Toujours exécuté, même si l'appel LLM a échoué ci-dessus : les
    # découvertes locales (linter + patterns) doivent quand même passer par
    # le filtrage/priorisation pour alimenter labels/check/auto-approve.
    line_contents = {(payload.filename, n): c for n, c in added_lines.items()}
    hallucination_check = filter_hallucinations(all_issues, line_contents, min_confidence=settings.min_issue_confidence)
    flagged_count = len(hallucination_check.flagged_issues)
    final_issues = filter_and_prioritize(hallucination_check.trusted_issues, max_comments=settings.max_comments_per_review)

    labels = determine_labels(final_issues)
    conclusion, check_summary = determine_conclusion(final_issues)
    auto_approve = should_auto_approve(final_issues, lines_changed=len(lines))

    return {
        "error": error,
        "llm_summary": result_summary,
        "llm_provider": settings.llm_provider,
        "lint_issues": [asdict(i) for i in lint_issues],
        "pattern_matches": [asdict(m) for m in pattern_matches],
        "issues": [asdict(i) for i in final_issues],
        "flagged_issues_count": flagged_count,
        "labels": labels,
        "check": {"conclusion": conclusion, "summary": check_summary},
        "auto_approve": auto_approve,
    }


