from app.auto_approve import should_auto_approve
from app.llm.base import ReviewIssue


def _issue(severity):
    return ReviewIssue(filename="a.py", line=1, severity=severity, message="msg")


def test_small_clean_pr_is_auto_approved():
    assert should_auto_approve([], lines_changed=10, max_lines=30) is True


def test_small_pr_with_info_only_is_still_auto_approved():
    assert should_auto_approve([_issue("info")], lines_changed=10, max_lines=30) is True


def test_small_pr_with_warning_is_not_auto_approved():
    assert should_auto_approve([_issue("warning")], lines_changed=10, max_lines=30) is False


def test_small_pr_with_critical_is_not_auto_approved():
    assert should_auto_approve([_issue("critical")], lines_changed=10, max_lines=30) is False


def test_clean_but_too_large_pr_is_not_auto_approved():
    assert should_auto_approve([], lines_changed=200, max_lines=30) is False


def test_pr_exactly_at_threshold_is_still_eligible():
    assert should_auto_approve([], lines_changed=30, max_lines=30) is True
