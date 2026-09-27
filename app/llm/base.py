"""
AAR-18 : Interface commune pour les fournisseurs de LLM (OpenAI / Anthropic),
conforme à l'interface `LLMProvider` du diagramme de classes.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ReviewIssue:
    filename: str
    line: int
    severity: str  # "critical" | "warning" | "info"
    message: str
    suggestion: str | None = None
    confidence: str = "medium"  # "high" | "medium" | "low" — AAR-33, auto-déclaré par le LLM


@dataclass
class ReviewResult:
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""


class LLMProvider(ABC):
    """Tout fournisseur LLM doit savoir analyser un prompt et renvoyer un ReviewResult structuré."""

    @abstractmethod
    async def analyze(self, system_prompt: str, user_prompt: str) -> ReviewResult:
        ...


def parse_review_json(raw_content: str) -> ReviewResult:
    """
    Transforme la réponse JSON brute du LLM (US 2.2 : réponse structurée)
    en ReviewResult. Dégrade proprement (liste vide) si le JSON est
    malformé, plutôt que de lever une exception qui casserait tout le
    pipeline de revue pour une seule PR.
    """
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        return ReviewResult(issues=[], summary="", raw_response=raw_content)

    issues = [
        ReviewIssue(
            filename=item.get("filename", ""),
            line=int(item.get("line", 0) or 0),
            severity=item.get("severity", "info"),
            message=item.get("message", ""),
            suggestion=item.get("suggestion"),
            confidence=item.get("confidence", "medium"),
        )
        for item in data.get("issues", [])
        if isinstance(item, dict)
    ]
    return ReviewResult(issues=issues, summary=data.get("summary", ""), raw_response=raw_content)
