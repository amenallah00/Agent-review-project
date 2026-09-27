from app.llm.base import ReviewIssue
from app.suggestion_formatter import format_comment_body


def test_comment_without_suggestion_has_no_code_block():
    issue = ReviewIssue(filename="a.py", line=1, severity="warning", message="Nom de variable peu clair")
    body = format_comment_body(issue)
    assert "```suggestion" not in body
    assert "Nom de variable peu clair" in body


def test_comment_with_suggestion_includes_applicable_code_block():
    issue = ReviewIssue(
        filename="a.py", line=1, severity="critical",
        message="Requête vulnérable à l'injection SQL",
        suggestion='query = "SELECT * FROM users WHERE id = %s"',
    )
    body = format_comment_body(issue)
    assert "```suggestion" in body
    assert 'query = "SELECT * FROM users WHERE id = %s"' in body
    assert body.strip().endswith("```")


def test_severity_emoji_present_for_each_level():
    for severity in ("critical", "warning", "info"):
        issue = ReviewIssue(filename="a.py", line=1, severity=severity, message="test")
        body = format_comment_body(issue)
        assert severity.upper() in body
