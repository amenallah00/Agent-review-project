"""
Correctif sécurité (post-Niveau 2) : convertit les découvertes locales
déterministes — linter (AAR-15) et détection de patterns (AAR-16) — en
`ReviewIssue`, pour qu'elles suivent le même pipeline que les issues du LLM
(anti-hallucination AAR-33, filtrage/priorisation AAR-20) et surtout pour
qu'elles alimentent TOUJOURS le check run / les labels / l'auto-approbation,
même si l'appel LLM échoue ou n'a pas encore eu lieu.

`confidence="high"` : ces découvertes ne sont pas des suppositions du LLM,
ce sont des faits (pattern regex matché, règle de lint violée sur du code
réellement présent) — elles ne doivent jamais être écartées par le filtre
anti-hallucination (AAR-33), qui n'écarte que ce qui est incertain.
"""

from .linter import LintIssue
from .llm.base import ReviewIssue
from .pattern_detector import PatternMatch

_LINT_SEVERITY_MAP = {
    "error": "critical",
    "fatal": "critical",
    "warning": "warning",
    "convention": "info",
    "refactor": "info",
}


def lint_issues_to_review_issues(lint_issues: list[LintIssue]) -> list[ReviewIssue]:
    return [
        ReviewIssue(
            filename=issue.filename,
            line=issue.line,
            severity=_LINT_SEVERITY_MAP.get(issue.severity, "info"),
            message=f"[Linter/{issue.rule}] {issue.message}" if issue.rule else f"[Linter] {issue.message}",
            suggestion=None,
            confidence="high",
        )
        for issue in lint_issues
    ]


def pattern_matches_to_review_issues(pattern_matches: list[PatternMatch]) -> list[ReviewIssue]:
    return [
        ReviewIssue(
            filename=match.filename,
            line=match.line,
            severity=match.severity,
            message=f"[Pattern/{match.pattern_name}] {match.message}",
            suggestion=None,
            confidence="high",
        )
        for match in pattern_matches
    ]
