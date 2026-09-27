from app.check_run import determine_conclusion
from app.llm.base import ReviewIssue


def _issue(severity):
    return ReviewIssue(filename="a.py", line=1, severity=severity, message="msg")


def test_no_issues_gives_success():
    conclusion, summary = determine_conclusion([])
    assert conclusion == "success"


def test_critical_issue_gives_failure():
    conclusion, summary = determine_conclusion([_issue("critical")])
    assert conclusion == "failure"
    assert "critique" in summary.lower()


def test_warning_only_gives_neutral_not_failure():
    conclusion, summary = determine_conclusion([_issue("warning")])
    assert conclusion == "neutral"


def test_critical_takes_priority_over_warning_for_conclusion():
    conclusion, _ = determine_conclusion([_issue("warning"), _issue("critical")])
    assert conclusion == "failure"
