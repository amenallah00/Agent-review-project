"""
AAR-26 : Auto-approbation des PR mineures.

⚠️ Rappel important (cahier des charges, périmètre EXCLU) : "L'agent ne
fusionnera (merge) pas automatiquement les Pull Requests." Ce module
n'approuve JAMAIS de fusion — il soumet uniquement une review GitHub avec
`event=APPROVE`, ce qui est différent d'un merge : la décision finale de
fusionner reste humaine (ou soumise aux règles de branch protection du
dépôt, ex: "1 approbation requise" + tests CI).

Volontairement conservateur : n'approuve que si (a) aucun problème
"critical" ou "warning" n'a été détecté, ET (b) la PR reste sous un seuil
de lignes nettement plus strict que le seuil général de l'US 4.2 — une PR
vraiment "mineure" doit rester petite, pas juste "pas trop grosse".
Désactivable via `.reviewbot.yml` (AAR-28, `auto_approve_enabled: false`).
"""

from .llm.base import ReviewIssue

DEFAULT_MINOR_PR_MAX_LINES = 30
_BLOCKING_SEVERITIES = {"critical", "warning"}


def should_auto_approve(issues: list[ReviewIssue], lines_changed: int, max_lines: int = DEFAULT_MINOR_PR_MAX_LINES) -> bool:
    if lines_changed > max_lines:
        return False
    return not any(issue.severity in _BLOCKING_SEVERITIES for issue in issues)
