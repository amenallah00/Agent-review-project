"""
AAR-23 : Construction du résumé global de la revue (corps principal de la
Review GitHub) — combine le résumé donné par le LLM, un décompte des
problèmes par sévérité, les avertissements de troncature (Bug 1), et les
commentaires qui n'ont pas pu être attachés à une ligne précise (Bug 2).
"""

from .llm.base import ReviewIssue

SEVERITY_ORDER = ["critical", "warning", "info"]
SEVERITY_LABELS = {"critical": "Critique", "warning": "Avertissement", "info": "Information"}


def build_review_summary(
    llm_summaries: list[str],
    all_issues: list[ReviewIssue],
    global_issues: list[ReviewIssue],
    truncated_files: list[str],
    cost_skipped_files: list[str] | None = None,
    flagged_issues_count: int = 0,
) -> str:
    """
    `all_issues` : la totalité des issues retenues après filtrage (AAR-20),
    inline + globales confondues, pour le décompte par sévérité.
    `global_issues` : celles reconverties par le LineValidator (Bug 2).
    `cost_skipped_files` : fichiers non analysés car le plafond de chunks
    par revue a été atteint (AAR-34 [RISQUE]).
    `flagged_issues_count` : nombre d'observations écartées par le filtre
    anti-hallucination (AAR-33 [RISQUE]) — confiance faible ou non ancrées.
    """
    lines = ["## 🤖 Résumé de la revue automatisée\n"]

    combined_summary = " ".join(s for s in llm_summaries if s).strip()
    if combined_summary:
        lines.append(combined_summary)
        lines.append("")

    counts = {sev: sum(1 for i in all_issues if i.severity == sev) for sev in SEVERITY_ORDER}
    count_line = " · ".join(
        f"{SEVERITY_LABELS[sev]} : {counts[sev]}" for sev in SEVERITY_ORDER if counts[sev] > 0
    )
    lines.append(f"**Problèmes détectés** — {count_line}" if count_line else "✅ Aucun problème détecté sur le code modifié.")

    if truncated_files:
        lines.append("")
        lines.append(
            "⚠️ **Fichier(s) trop volumineux, analyse partielle** (Bug 1) : "
            + ", ".join(truncated_files)
        )

    if cost_skipped_files:
        lines.append("")
        lines.append(
            "💰 **Fichier(s) non analysés (plafond de coût atteint)** : "
            + ", ".join(cost_skipped_files)
            + " — augmentez `MAX_CHUNKS_PER_REVIEW` si nécessaire, ou scindez la PR."
        )

    if flagged_issues_count:
        lines.append("")
        lines.append(
            f"🔍 {flagged_issues_count} observation(s) supplémentaire(s) écartée(s) "
            "par le filtre anti-hallucination (confiance faible ou non vérifiable) — non affichées."
        )

    if global_issues:
        lines.append("\n---\n### Commentaires additionnels (hors diff)")
        lines.append(
            "_Ces observations concernent des lignes hors du diff analysé et n'ont pas pu être "
            "attachées à une ligne précise :_\n"
        )
        for issue in global_issues:
            lines.append(f"- **{issue.filename}** (ligne {issue.line}) — {issue.message}")

    return "\n".join(lines)
