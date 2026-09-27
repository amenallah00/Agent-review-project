import pytest

from app.diff_parser import FileChange, Hunk
from app.llm.base import ReviewIssue
from app.review_publisher import publish_review


class FakeGitHubClient:
    """Faux client GitHub : capture l'appel à create_review sans réseau."""

    def __init__(self):
        self.calls = []

    async def create_review(self, owner, repo, pr_number, comments, body="", event="COMMENT"):
        self.calls.append({
            "owner": owner, "repo": repo, "pr_number": pr_number,
            "comments": comments, "body": body, "event": event,
        })
        return {"id": 1}


def _file(filename: str, valid_line: int) -> FileChange:
    hunk = Hunk(header="@@", new_start=valid_line, content=f"+line {valid_line}")
    return FileChange(filename=filename, hunks=[hunk])


@pytest.mark.asyncio
async def test_publish_review_posts_valid_inline_comment_with_suggestion():
    client = FakeGitHubClient()
    files = [_file("app/db.py", 10)]
    issues = [
        ReviewIssue(
            filename="app/db.py", line=10, severity="critical",
            message="Injection SQL", suggestion="query = safe_query()",
        )
    ]

    await publish_review(client, "smartovate", "repo", 42, files, issues, ["Résumé LLM"], [])

    assert len(client.calls) == 1
    comments = client.calls[0]["comments"]
    assert len(comments) == 1
    assert comments[0]["path"] == "app/db.py"
    assert comments[0]["line"] == 10
    assert comments[0]["side"] == "RIGHT"
    assert "```suggestion" in comments[0]["body"]


@pytest.mark.asyncio
async def test_publish_review_moves_invalid_line_issue_to_summary_not_inline():
    client = FakeGitHubClient()
    files = [_file("app/db.py", 10)]
    issues = [
        ReviewIssue(filename="app/db.py", line=999, severity="warning", message="ligne hors diff (Bug 2)"),
    ]

    await publish_review(client, "smartovate", "repo", 42, files, issues, [], [])

    comments = client.calls[0]["comments"]
    body = client.calls[0]["body"]
    assert comments == []  # Bug 2 : pas de commentaire inline sur une ligne inexistante
    assert "ligne hors diff (Bug 2)" in body  # reconverti en commentaire global


@pytest.mark.asyncio
async def test_publish_review_skips_entirely_when_nothing_to_report():
    client = FakeGitHubClient()
    result = await publish_review(client, "smartovate", "repo", 42, [], [], [], [])
    assert result is None
    assert client.calls == []


@pytest.mark.asyncio
async def test_publish_review_with_approve_event_posts_even_without_issues():
    """AAR-26 : une auto-approbation doit être postée même si issues est vide."""
    client = FakeGitHubClient()
    await publish_review(
        client, "smartovate", "repo", 42, files=[], issues=[], llm_summaries=["Rien à signaler."],
        truncated_files=[], event="APPROVE",
    )
    assert len(client.calls) == 1
