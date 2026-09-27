from app.label_manager import LABEL_LOOKS_GOOD, LABEL_NEEDS_CHANGES, LABEL_SECURITY_RISK, determine_labels
from app.llm.base import ReviewIssue


def _issue(severity):
    return ReviewIssue(filename="a.py", line=1, severity=severity, message="msg")


def test_critical_issue_triggers_security_risk_and_needs_changes():
    labels = determine_labels([_issue("critical")])
    assert LABEL_SECURITY_RISK in labels
    assert LABEL_NEEDS_CHANGES in labels


def test_warning_only_triggers_needs_changes_not_security_risk():
    labels = determine_labels([_issue("warning")])
    assert labels == [LABEL_NEEDS_CHANGES]


def test_info_only_or_no_issues_triggers_looks_good():
    assert determine_labels([_issue("info")]) == [LABEL_LOOKS_GOOD]
    assert determine_labels([]) == [LABEL_LOOKS_GOOD]


def test_critical_takes_priority_over_warning():
    labels = determine_labels([_issue("warning"), _issue("critical")])
    assert LABEL_SECURITY_RISK in labels
