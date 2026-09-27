"""
AAR-29 : Métriques et statistiques de revue.

Stockage EN MÉMOIRE (process unique) — suffisant pour un tableau de bord
de stage sur une seule instance. À remplacer par une vraie base de données
(ou un backend partagé type Redis) si l'agent doit un jour tourner sur
plusieurs instances en parallèle, sinon chaque instance aurait ses propres
compteurs partiels.

Historique par revue ajouté pour alimenter le tableau de bord restylé
(inspiré de PRLens, cf. rapport de stage Ismail Mechkene, §3.7) : tendance
de score par dépôt et tableau "Recent reviews". Contrairement à PRLens,
`agent-review` n'a pas de base de données relationnelle — cet historique
reste donc, comme le reste des métriques, en mémoire et borné
(`_MAX_HISTORY`) pour éviter une fuite mémoire sur un process de longue
durée.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .llm.base import ReviewIssue

_MAX_HISTORY = 200

# Pénalités utilisées pour dériver un score de 0 à 100 à partir des issues
# d'une revue, dans le même esprit que le calcul décrit dans le rapport
# PRLens (§3.8.2) : pénalités cumulées par sévérité, clampées à 0.
_SEVERITY_PENALTY = {"critical": 25, "warning": 8, "info": 2}


def _compute_score(issues: list[ReviewIssue]) -> int:
    score = 100
    for issue in issues:
        score -= _SEVERITY_PENALTY.get(issue.severity, 2)
    return max(0, score)


def _categorize(issue: ReviewIssue) -> str:
    """
    Approximation des 5 dimensions PRLens (sécurité / qualité / performance /
    style / documentation) à partir de nos propres détecteurs. `agent-review`
    ne classe pas nativement ses issues par dimension (seulement par
    sévérité) : cette fonction dérive une catégorie plausible à partir du
    préfixe du message, pour l'affichage seulement.
    """
    msg = issue.message
    if msg.startswith("[Pattern/"):
        return "security"
    if msg.startswith("[Linter/"):
        return "documentation" if "docstring" in msg.lower() else "style"
    return "quality"


@dataclass
class ReviewRecord:
    repo: str
    pr_number: int
    pr_title: str
    score: int
    status: str  # "approved" | "changes_requested" | "commented"
    reviewed_at: str
    issues_by_category: dict

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "pr_number": self.pr_number,
            "pr_title": self.pr_title,
            "score": self.score,
            "status": self.status,
            "reviewed_at": self.reviewed_at,
            "issues_by_category": self.issues_by_category,
        }


@dataclass
class ReviewMetrics:
    total_reviews: int = 0
    total_issues_by_severity: Counter = field(default_factory=Counter)
    prs_auto_approved: int = 0
    prs_skipped_too_large: int = 0
    labels_applied: Counter = field(default_factory=Counter)
    recent_reviews: list = field(default_factory=list)  # list[ReviewRecord], plus récent en premier

    def record_review(
        self,
        issues: list[ReviewIssue],
        auto_approved: bool = False,
        repo: str = "",
        pr_number: int = 0,
        pr_title: str = "",
        conclusion: str = "neutral",
    ) -> None:
        self.total_reviews += 1
        for issue in issues:
            self.total_issues_by_severity[issue.severity] += 1
        if auto_approved:
            self.prs_auto_approved += 1

        status = {"success": "approved", "failure": "changes_requested"}.get(conclusion, "commented")
        categories = Counter(_categorize(i) for i in issues)
        record = ReviewRecord(
            repo=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            score=_compute_score(issues),
            status=status,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
            issues_by_category=dict(categories),
        )
        self.recent_reviews.insert(0, record)
        del self.recent_reviews[_MAX_HISTORY:]

    def record_skipped_too_large(self) -> None:
        self.prs_skipped_too_large += 1

    def record_labels(self, labels: list[str]) -> None:
        for label in labels:
            self.labels_applied[label] += 1

    def to_dict(self) -> dict:
        return {
            "total_reviews": self.total_reviews,
            "total_issues_by_severity": dict(self.total_issues_by_severity),
            "prs_auto_approved": self.prs_auto_approved,
            "prs_skipped_too_large": self.prs_skipped_too_large,
            "labels_applied": dict(self.labels_applied),
        }

    def average_score(self) -> int:
        if not self.recent_reviews:
            return 0
        return round(sum(r.score for r in self.recent_reviews) / len(self.recent_reviews))

    def repos_summary(self) -> list[dict]:
        by_repo: dict[str, list[ReviewRecord]] = {}
        for r in self.recent_reviews:
            by_repo.setdefault(r.repo, []).append(r)

        summary = []
        for repo, records in by_repo.items():
            avg = round(sum(r.score for r in records) / len(records))
            summary.append({
                "name": repo,
                "reviews_count": len(records),
                "average_score": avg,
                "active": True,
                "last_reviewed_at": records[0].reviewed_at,
            })
        summary.sort(key=lambda r: r["last_reviewed_at"], reverse=True)
        return summary

    def reviews_for_repo(self, repo: str) -> list[ReviewRecord]:
        return [r for r in self.recent_reviews if r.repo == repo]


# Instance partagée au niveau du module : un seul compteur pour tout le
# process (voir limitation multi-instance ci-dessus).
metrics = ReviewMetrics()
