"""
AAR-33 [RISQUE] Hallucinations LLM — Faux positifs dans la revue.

Complète le LineValidator (Bug 2, qui vérifie que la ligne EXISTE dans le
diff) par une vérification que le problème signalé est FONDÉ, pas inventé.
Deux mécanismes :

1. Confiance auto-déclarée par le LLM (`ReviewIssue.confidence`, cf.
   prompt_builder.py) — les issues "low" sont écartées par défaut.
2. Vérification d'ancrage (`is_grounded`) : si le message cite un
   identifiant entre backticks (ex: `user_id`), celui-ci doit apparaître
   réellement dans la ligne concernée — un LLM qui invente un nom de
   variable/fonction inexistant est un signe classique d'hallucination.
"""

import re
from dataclasses import dataclass

from .llm.base import ReviewIssue

_BACKTICK_RE = re.compile(r"`([^`]+)`")
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass
class HallucinationCheckResult:
    trusted_issues: list[ReviewIssue]
    flagged_issues: list[ReviewIssue]  # confiance insuffisante et/ou non ancré


def _extract_quoted_identifiers(message: str) -> list[str]:
    return _BACKTICK_RE.findall(message)


def is_grounded(issue: ReviewIssue, line_content: str | None) -> bool:
    """
    True si le message ne cite aucun identifiant entre backticks (rien à
    vérifier), OU si au moins un identifiant cité apparaît réellement dans
    la ligne. False seulement si des identifiants sont cités mais qu'AUCUN
    n'apparaît dans le code réel — signe probable d'hallucination.
    """
    identifiers = _extract_quoted_identifiers(issue.message)
    if not identifiers:
        return True
    if line_content is None:
        return True  # ligne inconnue (ex: commentaire déjà global) : pas de vérification possible
    return any(identifier in line_content for identifier in identifiers)


def filter_hallucinations(
    issues: list[ReviewIssue],
    line_contents: dict[tuple[str, int], str],
    min_confidence: str = "medium",
) -> HallucinationCheckResult:
    """
    `line_contents` : dict {(filename, line): contenu réel de la ligne},
    construit à partir des `FileChange` du diff (voir review_engine.py).
    """
    min_rank = _CONFIDENCE_RANK.get(min_confidence, 1)

    trusted: list[ReviewIssue] = []
    flagged: list[ReviewIssue] = []

    for issue in issues:
        line_content = line_contents.get((issue.filename, issue.line))
        grounded = is_grounded(issue, line_content)
        confidence_ok = _CONFIDENCE_RANK.get(issue.confidence, 1) >= min_rank

        if grounded and confidence_ok:
            trusted.append(issue)
        else:
            flagged.append(issue)

    return HallucinationCheckResult(trusted_issues=trusted, flagged_issues=flagged)
