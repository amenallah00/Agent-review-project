"""
Modèle de données relationnel du tableau de bord (cf. rapport PRLens §3.6,
fig. 3.5) : User -> Installation -> Review -> ReviewComment.

Rebrandé CodeSentinel, mêmes quatre entités et mêmes relations que le
rapport de stage : un utilisateur possède plusieurs installations (un dépôt
GitHub rattaché à son compte), chaque installation accumule un historique
de revues, chaque revue détaille ses commentaires individuels. Suppression
en cascade à chaque niveau (cascade="all, delete-orphan").
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    handle: Mapped[str] = mapped_column(String(120))
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Seul mécanisme d'autorisation du système (cf. rapport §3.9.2) : relu en
    # base à chaque requête, jamais porté comme revendication dans le JWT.
    role: Mapped[str] = mapped_column(String(20), default="user")
    reviews_used: Mapped[int] = mapped_column(Integer, default=0)
    # Jeton d'accès GitHub de l'utilisateur (scope repo/read:user), utilisé
    # uniquement côté serveur pour lister ses dépôts (jamais exposé au client).
    github_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    installations: Mapped[list["Installation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "github_id": self.github_id,
            "handle": self.handle,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "reviews_used": self.reviews_used,
        }


class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (UniqueConstraint("user_id", "repo_name", name="uq_user_repo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    repo_name: Mapped[str] = mapped_column(String(200))  # "owner/repo"
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=True)

    min_severity: Mapped[str] = mapped_column(String(20), default="warning")
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["python", "javascript", "typescript"])
    excluded_files: Mapped[list] = mapped_column(JSON, default=list)
    approve_threshold: Mapped[int] = mapped_column(Integer, default=80)
    changes_threshold: Mapped[int] = mapped_column(Integer, default=50)
    reviewer_map: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="installations")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="installation", cascade="all, delete-orphan", order_by="(desc(Review.reviewed_at), desc(Review.id))"
    )

    def to_dict(self) -> dict:
        return {
            "name": self.repo_name,
            "visibility": self.visibility,
            "active": self.active,
            "min_severity": self.min_severity,
            "languages": self.languages,
            "excluded_files": self.excluded_files,
            "approve_threshold": self.approve_threshold,
            "changes_threshold": self.changes_threshold,
            "reviewer_map": self.reviewer_map,
        }


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    installation_id: Mapped[int] = mapped_column(ForeignKey("installations.id"))
    pr_number: Mapped[int] = mapped_column(Integer)
    pr_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="commented")  # approved | changes_requested | commented
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    installation: Mapped["Installation"] = relationship(back_populates="reviews")
    comments: Mapped[list["ReviewComment"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        by_cat: dict[str, int] = {}
        for c in self.comments:
            by_cat[c.type] = by_cat.get(c.type, 0) + 1
        return {
            "pr_number": self.pr_number,
            "pr_title": self.pr_title,
            "score": self.score,
            "status": self.status,
            "reviewed_at": self.reviewed_at.isoformat(),
            "issues_by_category": by_cat,
            "repo": self.installation.repo_name if self.installation else None,
        }


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"))
    file_path: Mapped[str] = mapped_column(String(500))
    line: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(30), default="quality")  # security|quality|performance|style|documentation
    severity: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    review: Mapped["Review"] = relationship(back_populates="comments")
