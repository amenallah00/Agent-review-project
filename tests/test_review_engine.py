
from app import review_engine
from app.diff_parser import parse_diff
from app.llm.base import ReviewResult

_DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,1 +1,3 @@
+import os
+api_key = "sk-hardcoded-secret-value-123"
+print("debug")
"""


class _FakeGitHubClient:
    async def get_file_content(self, owner, repo, filename, ref=None):
        return 'api_key = "sk-hardcoded-secret-value-123"\nprint("debug")\n'


class _FailingProvider:
    async def analyze(self, system_prompt, user_prompt):
        raise RuntimeError("429 rate limit")


class _WorkingProvider:
    async def analyze(self, system_prompt, user_prompt):
        return ReviewResult(issues=[], summary="Résumé du LLM")


async def test_llm_failure_never_drops_local_findings(monkeypatch):
    """
    Correctif sécurité : si l'appel LLM échoue, les découvertes locales
    déterministes (linter + patterns critiques, ex: secret codé en dur)
    doivent quand même apparaître dans le ReviewOutcome final — sinon une
    PR avec un vrai problème CRITICAL pourrait être auto-approuvée /
    obtenir un check "success" simplement parce que le LLM était en panne.
    """
    monkeypatch.setattr(review_engine, "get_llm_provider", lambda: _FailingProvider())
    files = parse_diff(_DIFF)

    outcome = await review_engine.review_pull_request(_FakeGitHubClient(), "acme", "repo", "deadbeef", files)

    assert outcome.llm_failed is True
    messages = [issue.message for issue in outcome.issues]
    assert any("[Pattern/hardcoded_secret]" in m for m in messages)
    assert any(issue.severity == "critical" for issue in outcome.issues)
    assert any("échec" in s.lower() or "échoué" in s.lower() for s in outcome.llm_summaries)


async def test_llm_success_merges_local_and_llm_findings(monkeypatch):
    monkeypatch.setattr(review_engine, "get_llm_provider", lambda: _WorkingProvider())
    files = parse_diff(_DIFF)

    outcome = await review_engine.review_pull_request(_FakeGitHubClient(), "acme", "repo", "deadbeef", files)

    assert outcome.llm_failed is False
    assert "Résumé du LLM" in outcome.llm_summaries
    messages = [issue.message for issue in outcome.issues]
    assert any("[Pattern/hardcoded_secret]" in m for m in messages)
