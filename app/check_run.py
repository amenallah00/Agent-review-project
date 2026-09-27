"""
AAR-25 : Statut de vérification (Check Run) exploitable pour configurer un
"required status check" sur la branche protégée.

Important : la configuration de la branch protection elle-même (rendre ce
check "obligatoire") se fait manuellement dans les paramètres du dépôt
GitHub (Settings > Branches) — voir README.md — ce module se contente de
publier un résultat correct et exploitable, il ne peut pas configurer la
branch protection à la place de l'utilisateur (l'API GitHub l'exige).
"""

from .llm.base import ReviewIssue

CHECK_NAME = "AI Code Review"


def determine_conclusion(issues: list[ReviewIssue]) -> tuple[str, str]:
    """
    Retourne (conclusion, résumé) au format attendu par l'API GitHub Checks.
    conclusion : "success" | "neutral" | "failure"
    """
    critical_count = sum(1 for i in issues if i.severity == "critical")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    if critical_count > 0:
        return "failure", f"{critical_count} problème(s) critique(s) détecté(s) — correction requise."
    if warning_count > 0:
        return "neutral", f"{warning_count} avertissement(s) détecté(s) — à examiner."
    return "success", "Aucun problème détecté."
