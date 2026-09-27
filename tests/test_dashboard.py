"""
Tests du tableau de bord CodeSentinel : pages HTML (landing + dashboard
shell), testeur de pipeline (/api/test-review, sans DB ni auth), et l'API
REST persistée (auth par jeton de session, base SQLite en mémoire isolée
par test — cf. rapport §4.6.1 : les routes protégées par rôle sont testées
contre une vraie base plutôt que simulées, car la règle à vérifier porte
précisément sur le rôle stocké en base).
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_session_token
from app.database import Base, get_db
from app.db_models import User
from app.main import app

client = TestClient(app)


@pytest.fixture()
def db_session():
    """Base SQLite en mémoire, isolée par test, injectée via `app.dependency_overrides`."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app import db_models as _db_models  # noqa: F401 — enregistre les modèles sur Base avant create_all
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()


@dataclass
class AuthedClient:
    user: User
    token: str

    def get(self, url, **kw):
        return client.get(url, headers={"Authorization": f"Bearer {self.token}"}, **kw)

    def post(self, url, **kw):
        return client.post(url, headers={"Authorization": f"Bearer {self.token}"}, **kw)

    def put(self, url, **kw):
        return client.put(url, headers={"Authorization": f"Bearer {self.token}"}, **kw)

    def delete(self, url, **kw):
        return client.delete(url, headers={"Authorization": f"Bearer {self.token}"}, **kw)


@pytest.fixture()
def as_user(db_session):
    user = User(github_id=101, handle="dana", name="Dana Kessler", role="user", github_token="fake")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return AuthedClient(user=user, token=create_session_token(user))


@pytest.fixture()
def as_admin(db_session):
    user = User(github_id=1, handle="ismail", name="Ismail Mechkene", role="admin", github_token="fake")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return AuthedClient(user=user, token=create_session_token(user))


# --------------------------------------------------------------------------
# Pages HTML publiques
# --------------------------------------------------------------------------

def test_root_serves_the_built_react_frontend_shell():
    """
    Le contenu réel (landing, login GitHub, dashboard, etc.) est rendu
    côté client par React (frontend/) — voir app/main.py, route SPA de
    repli. Le serveur ne fait que servir le shell HTML une fois le build
    Vite généré (`npm run build`), donc ce test s'adapte aux deux cas.
    """
    resp = client.get("/")
    if resp.status_code == 404:
        pytest.skip("frontend/dist absent — lancez `npm run build` dans frontend/ pour ce test")
    assert resp.status_code == 200
    assert "<div id=\"root\">" in resp.text


def test_dashboard_route_falls_back_to_the_same_spa_shell():
    """`/dashboard` (route côté client React Router) doit aussi recevoir le shell, pas un 404."""
    resp = client.get("/dashboard")
    if resp.status_code == 404:
        pytest.skip("frontend/dist absent — lancez `npm run build` dans frontend/ pour ce test")
    assert resp.status_code == 200
    assert "<div id=\"root\">" in resp.text


def test_health_check_still_works():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --------------------------------------------------------------------------
# Authentification : toute route /api/* liée à un compte exige un jeton.
# --------------------------------------------------------------------------

def test_api_user_requires_authentication():
    assert client.get("/api/user").status_code == 401


def test_api_user_rejects_garbage_token():
    resp = client.get("/api/user", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_oauth_start_without_client_id_returns_503(monkeypatch):
    monkeypatch.setattr("app.auth.settings.github_oauth_client_id", None)
    resp = client.get("/auth/github", follow_redirects=False)
    assert resp.status_code == 503


# --------------------------------------------------------------------------
# API REST persistée (dépôts, revues, statistiques)
# --------------------------------------------------------------------------

def test_api_user_returns_profile(as_user):
    resp = as_user.get("/api/user")
    assert resp.status_code == 200
    data = resp.json()
    assert data["handle"] == "dana"
    assert data["role"] == "user"


def test_repos_empty_by_default(as_user):
    resp = as_user.get("/api/repos")
    assert resp.status_code == 200
    assert resp.json() == {"repos": [], "recent_reviews": []}


def test_connect_a_repo_then_see_it_listed(as_user):
    resp = as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    assert resp.status_code == 200
    assert resp.json()["name"] == "acme/api-gateway"

    repos_resp = as_user.get("/api/repos")
    assert repos_resp.status_code == 200
    assert [r["name"] for r in repos_resp.json()["repos"]] == ["acme/api-gateway"]


def test_connecting_the_same_repo_twice_is_rejected(as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    resp = as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    assert resp.status_code == 409


def test_repo_detail_404_for_unconnected_repo(as_user):
    resp = as_user.get("/api/repos/nobody%2Fnothing")
    assert resp.status_code == 404


def test_update_repo_settings(as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    resp = as_user.put("/api/repos/acme%2Fapi-gateway/settings", json={"approve_threshold": 95})
    assert resp.status_code == 200
    assert resp.json()["approve_threshold"] == 95


def test_toggle_repo_active(as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    resp = as_user.put("/api/repos/acme%2Fapi-gateway/active", json={"active": False})
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_disconnect_repo_removes_it(as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    resp = as_user.delete("/api/repos/acme%2Fapi-gateway")
    assert resp.status_code == 200
    assert as_user.get("/api/repos").json()["repos"] == []


def test_a_users_repos_are_isolated_from_another_users(db_session, as_user):
    other = User(github_id=202, handle="karasaki", role="user")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_client = AuthedClient(user=other, token=create_session_token(other))

    as_user.post("/api/repos/acme%2Fapi-gateway/enable")

    assert as_user.get("/api/repos").json()["repos"][0]["name"] == "acme/api-gateway"
    assert other_client.get("/api/repos").json()["repos"] == []


def test_api_stats_reflects_connected_repos(as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")
    resp = as_user.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repos_connected"] == 1
    assert data["prs_reviewed"] == 0
    assert data["reviews_remaining"] == 50  # FREE_TIER_REVIEW_LIMIT par défaut


# --------------------------------------------------------------------------
# Espace d'administration (cf. rapport §3.9.2 : rôle relu en base, lecture seule)
# --------------------------------------------------------------------------

def test_admin_routes_reject_anonymous_caller():
    assert client.get("/api/admin/stats").status_code == 401


def test_admin_routes_reject_ordinary_user(as_user):
    assert as_user.get("/api/admin/stats").status_code == 403
    assert as_user.get("/api/admin/users").status_code == 403


def test_admin_routes_accept_administrator(as_admin, as_user):
    as_user.post("/api/repos/acme%2Fapi-gateway/enable")

    resp = as_admin.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["users"] == 2  # l'admin + l'utilisateur créé par as_user
    assert data["repos_connected"] == 1

    users_resp = as_admin.get("/api/admin/users")
    assert users_resp.status_code == 200
    assert any(u["handle"] == "dana" for u in users_resp.json()["users"])


# --------------------------------------------------------------------------
# Testeur de pipeline (/api/test-review) — sandbox sans DB ni compte, inchangé
# --------------------------------------------------------------------------

def test_api_config_returns_expected_keys():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("max_pr_lines", "max_comments_per_review", "llm_provider", "auto_approve_enabled"):
        assert key in data


def test_api_metrics_returns_expected_keys():
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_reviews", "total_issues_by_severity", "prs_auto_approved"):
        assert key in data


def test_api_test_review_runs_full_pipeline_with_fake_llm(monkeypatch):
    from app.llm.base import ReviewIssue, ReviewResult

    class FakeProvider:
        async def analyze(self, system_prompt, user_prompt):
            return ReviewResult(
                issues=[ReviewIssue(filename="example.py", line=1, severity="critical",
                                     message="Injection SQL détectée", suggestion="query = safe()")],
                summary="Une vulnérabilité critique a été trouvée.",
            )

    monkeypatch.setattr("app.dashboard.get_llm_provider", lambda: FakeProvider())

    resp = client.post("/api/test-review", json={
        "filename": "example.py",
        "code": 'query = "SELECT * FROM users WHERE id=" + user_id',
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is None
    assert any(i["message"] == "Injection SQL détectée" and i["severity"] == "critical" for i in data["issues"])
    assert any("[Pattern/sql_string_concat]" in i["message"] for i in data["issues"])
    assert "security-risk" in data["labels"]
    assert data["check"]["conclusion"] == "failure"
    assert data["auto_approve"] is False


def test_api_test_review_returns_error_field_when_llm_fails(monkeypatch):
    class FailingProvider:
        async def analyze(self, system_prompt, user_prompt):
            raise RuntimeError("clé API invalide")

    monkeypatch.setattr("app.dashboard.get_llm_provider", lambda: FailingProvider())

    resp = client.post("/api/test-review", json={
        "filename": "a.py",
        "code": 'query = "SELECT * FROM users WHERE id=" + user_id',
    })
    assert resp.status_code == 200  # jamais un 500 : outil de diagnostic, doit toujours répondre
    data = resp.json()
    assert data["error"] is not None
    assert "clé API invalide" in data["error"]
    assert any("[Pattern/sql_string_concat]" in i["message"] for i in data["issues"])
    assert "security-risk" in data["labels"]
