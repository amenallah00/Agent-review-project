"""
AAR-24 : Ajout automatique de labels sur la PR selon la qualité détectée
par la revue (issues restantes après filtrage/priorisation, AAR-20).
"""

from .llm.base import ReviewIssue

LABEL_SECURITY_RISK = "security-risk"
LABEL_NEEDS_CHANGES = "needs-changes"
LABEL_LOOKS_GOOD = "looks-good"


def determine_labels(issues: list[ReviewIssue]) -> list[str]:
    """
    - Au moins un problème "critical" -> "security-risk" + "needs-changes"
    - Au moins un "warning" (mais aucun critical) -> "needs-changes"
    - Aucun problème bloquant -> "looks-good"
    """
    severities = {issue.severity for issue in issues}

    if "critical" in severities:
        return [LABEL_SECURITY_RISK, LABEL_NEEDS_CHANGES]
    if "warning" in severities:
        return [LABEL_NEEDS_CHANGES]
    return [LABEL_LOOKS_GOOD]
