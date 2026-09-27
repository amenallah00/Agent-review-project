"""
AAR-20 : Filtrage et priorisation des commentaires générés par le LLM,
avant publication sur GitHub (US 3.1, ticket ultérieur) — évite de spammer
une PR avec trop de commentaires et priorise les problèmes les plus sérieux,
en complément du garde-fou de taille de PR (US 4.2).
"""

from .llm.base import ReviewIssue

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def deduplicate(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    """
    Retire les doublons : même fichier + même ligne + début de message
    identique (le LLM peut parfois répéter un même problème dans son
    résumé et dans sa liste d'issues, ou entre deux chunks qui se chevauchent
    légèrement).
    """
    seen: set[tuple[str, int, str]] = set()
    result: list[ReviewIssue] = []
    for issue in issues:
        key = (issue.filename, issue.line, issue.message.strip().lower()[:80])
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def prioritize(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    """Trie par sévérité (critical > warning > info), puis fichier/ligne pour un ordre stable et lisible."""
    return sorted(issues, key=lambda i: (SEVERITY_ORDER.get(i.severity, 3), i.filename, i.line))


def filter_and_prioritize(issues: list[ReviewIssue], max_comments: int = 15) -> list[ReviewIssue]:
    """
    Pipeline complet : déduplique, priorise, puis plafonne au nombre maximal
    de commentaires à poster sur une seule PR. Les problèmes "critical" sont
    toujours inclus en priorité, même si ça implique de couper plus de
    commentaires "info" pour respecter le plafond.
    """
    unique = deduplicate(issues)
    ranked = prioritize(unique)
    return ranked[:max_comments]
