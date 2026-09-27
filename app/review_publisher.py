"""
AAR-21 : Publication des commentaires de revue sur GitHub (US 3.1) —
assemble la validation des lignes (Bug 2), le formatage des suggestions
(AAR-22) et le résumé global (AAR-23) en un seul appel à l'API Review.
"""

import logging

from .diff_parser import FileChange
from .github_app import GitHubClient
from .line_validator import validate_issues
from .llm.base import ReviewIssue
from .review_summary import build_review_summary
from .suggestion_formatter import format_comment_body

logger = logging.getLogger("agent-review.review_publisher")


async def publish_review(
    client: GitHubClient,
    owner: str,
    repo: str,
    pr_number: int,
    files: list[FileChange],
    issues: list[ReviewIssue],
    llm_summaries: list[str],
    truncated_files: list[str],
    event: str = "COMMENT",
    cost_skipped_files: list[str] | None = None,
    flagged_issues_count: int = 0,
) -> dict | None:
    """
    Poste la revue complète sur GitHub : commentaires inline pour les
    lignes valides, résumé global (incluant les problèmes non attachables
    à une ligne précise, Bug 2, ainsi que les avertissements AAR-33/34).
    Si rien à signaler ET event="COMMENT", ne poste rien — mais une
    auto-approbation (event="APPROVE", AAR-26) est toujours postée, même
    sans issues, pour que l'approbation soit visible.
    """
    if event == "COMMENT" and not issues and not truncated_files and not cost_skipped_files:
        logger.info("Aucune issue à publier pour la PR #%s (code propre)", pr_number)
        return None

    validation = validate_issues(issues, files)

    if validation.invalid_issues:
        logger.warning(
            "Bug 2 évité : %d commentaire(s) reconverti(s) en commentaire global (ligne hors diff)",
            len(validation.invalid_issues),
        )

    inline_comments = [
        {
            "path": issue.filename,
            "line": issue.line,
            "side": "RIGHT",
            "body": format_comment_body(issue),
        }
        for issue in validation.valid_issues
    ]

    summary_body = build_review_summary(
        llm_summaries=llm_summaries,
        all_issues=issues,
        global_issues=validation.invalid_issues,
        truncated_files=truncated_files,
        cost_skipped_files=cost_skipped_files,
        flagged_issues_count=flagged_issues_count,
    )

    logger.info(
        "Publication de la revue PR #%s : %d commentaire(s) inline, %d commentaire(s) global(aux)",
        pr_number, len(inline_comments), len(validation.invalid_issues),
    )

    return await client.create_review(owner, repo, pr_number, comments=inline_comments, body=summary_body, event=event)
