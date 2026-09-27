from app.comment_filter import deduplicate, filter_and_prioritize, prioritize
from app.llm.base import ReviewIssue


def _issue(filename="a.py", line=1, severity="info", message="msg"):
    return ReviewIssue(filename=filename, line=line, severity=severity, message=message)


def test_deduplicate_removes_exact_duplicates():
    issues = [
        _issue(line=10, message="Risque d'injection SQL"),
        _issue(line=10, message="Risque d'injection SQL"),
    ]
    result = deduplicate(issues)
    assert len(result) == 1


def test_deduplicate_keeps_different_lines():
    issues = [_issue(line=10), _issue(line=20)]
    result = deduplicate(issues)
    assert len(result) == 2


def test_prioritize_orders_by_severity():
    issues = [
        _issue(severity="info", line=1),
        _issue(severity="critical", line=2),
        _issue(severity="warning", line=3),
    ]
    result = prioritize(issues)
    assert [i.severity for i in result] == ["critical", "warning", "info"]


def test_filter_and_prioritize_caps_max_comments():
    issues = [_issue(line=i, severity="info") for i in range(20)]
    result = filter_and_prioritize(issues, max_comments=5)
    assert len(result) == 5


def test_filter_and_prioritize_keeps_critical_over_cap():
    issues = [_issue(line=i, severity="info") for i in range(10)]
    issues.append(_issue(line=99, severity="critical", message="important"))
    result = filter_and_prioritize(issues, max_comments=3)
    assert any(i.severity == "critical" for i in result)
