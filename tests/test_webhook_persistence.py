"""
Vérifie que le webhook persiste les revues en base pour les dépôts
connectés au tableau de bord (cf. rapport §3.6, §4.5.2), sans dépendre de
la présence d'un compte connecté (comportement inchangé du mode Actions).
"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app import main
from app.config_loader import default_config
from app.database import Base
from app.db_models import Installation, Review, User
from app.llm.base import ReviewIssue
from app.review_engine import ReviewOutcome

client = TestClient(main.app)

WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app import db_models as _db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(main, "SessionLocal", TestingSessionLocal)

    session = TestingSessionLocal()
    yield session
    session.close()


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _pr_payload(pr_number: int = 7) -> bytes:
    payload = {
        "action": "opened",
        "installation": {"id": 1},
        "repository": {"name": "demo-repo", "owner": {"login": "acme"}},
        "pull_request": {"number": pr_number, "title": "Add feature", "head": {"sha": "abc123"}},
        "sender": {"type": "User"},
    }
    return json.dumps(payload).encode()


def _post_webhook(body: bytes, monkeypatch, issues=None):
    monkeypatch.setattr("app.main.settings.github_webhook_secret", WEBHOOK_SECRET)

    async def fake_review(*a, **kw):
        return ReviewOutcome(issues=issues or [])

    with patch("app.main.get_installation_token", AsyncMock(return_value="tok")), \
         patch("app.main.GitHubClient") as MockClient, \
         patch("app.main.review_pull_request", fake_review), \
         patch("app.main.load_repo_config", AsyncMock(return_value=default_config())), \
         patch("app.main.publish_review", AsyncMock()):
        instance = MockClient.return_value
        instance.get_diff = AsyncMock(return_value="")
        instance.post_issue_comment = AsyncMock()
        instance.add_labels = AsyncMock()
        instance.create_check_run = AsyncMock()
        return client.post("/webhook", data=body, headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _sign(body),
            "Content-Type": "application/json",
        })


def test_webhook_without_connected_installation_does_not_touch_db(db_session, monkeypatch):
    """Comportement inchangé : un dépôt piloté uniquement en mode Actions n'a pas de ligne à persister."""
    resp = _post_webhook(_pr_payload(), monkeypatch)
    assert resp.status_code == 200
    assert db_session.query(Review).count() == 0


def test_webhook_persists_review_for_connected_installation(db_session, monkeypatch):
    user = User(github_id=42, handle="dana", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    inst = Installation(user_id=user.id, repo_name="acme/demo-repo", active=True)
    db_session.add(inst)
    db_session.commit()

    issues = [ReviewIssue(filename="app.py", line=3, severity="critical", message="[Pattern/sql_string_concat] SQL injection")]
    resp = _post_webhook(_pr_payload(pr_number=7), monkeypatch, issues=issues)
    assert resp.status_code == 200

    reviews = db_session.query(Review).all()
    assert len(reviews) == 1
    assert reviews[0].pr_number == 7
    assert reviews[0].status == "changes_requested"
    assert len(reviews[0].comments) == 1
    assert reviews[0].comments[0].severity == "critical"

    db_session.refresh(user)
    assert user.reviews_used == 1


def test_webhook_skips_review_when_installation_inactive(db_session, monkeypatch):
    user = User(github_id=42, handle="dana", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    inst = Installation(user_id=user.id, repo_name="acme/demo-repo", active=False)
    db_session.add(inst)
    db_session.commit()

    resp = _post_webhook(_pr_payload(), monkeypatch)
    assert resp.status_code == 200
    assert db_session.query(Review).count() == 0


def test_webhook_blocks_review_once_quota_exhausted(db_session, monkeypatch):
    monkeypatch.setattr("app.main.settings.free_tier_review_limit", 1)
    user = User(github_id=42, handle="dana", role="user", reviews_used=1)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    inst = Installation(user_id=user.id, repo_name="acme/demo-repo", active=True)
    db_session.add(inst)
    db_session.commit()

    resp = _post_webhook(_pr_payload(), monkeypatch)
    assert resp.status_code == 200
    assert db_session.query(Review).count() == 0


def test_webhook_never_quota_blocks_admin_accounts(db_session, monkeypatch):
    monkeypatch.setattr("app.main.settings.free_tier_review_limit", 1)
    admin = User(github_id=1, handle="ismail", role="admin", reviews_used=5)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    inst = Installation(user_id=admin.id, repo_name="acme/demo-repo", active=True)
    db_session.add(inst)
    db_session.commit()

    resp = _post_webhook(_pr_payload(), monkeypatch)
    assert resp.status_code == 200
    assert db_session.query(Review).count() == 1
