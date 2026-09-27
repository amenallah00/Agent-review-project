from app.llm.base import ReviewIssue
from app.metrics import ReviewMetrics


def _issue(severity):
    return ReviewIssue(filename="a.py", line=1, severity=severity, message="msg")


def test_record_review_increments_total_and_severity_counts():
    m = ReviewMetrics()
    m.record_review([_issue("critical"), _issue("critical"), _issue("warning")])
    assert m.total_reviews == 1
    assert m.total_issues_by_severity["critical"] == 2
    assert m.total_issues_by_severity["warning"] == 1


def test_record_review_tracks_auto_approved_count():
    m = ReviewMetrics()
    m.record_review([], auto_approved=True)
    m.record_review([_issue("warning")], auto_approved=False)
    assert m.prs_auto_approved == 1
    assert m.total_reviews == 2


def test_record_skipped_too_large():
    m = ReviewMetrics()
    m.record_skipped_too_large()
    m.record_skipped_too_large()
    assert m.prs_skipped_too_large == 2


def test_record_labels_accumulates_counts():
    m = ReviewMetrics()
    m.record_labels(["needs-changes", "security-risk"])
    m.record_labels(["needs-changes"])
    assert m.labels_applied["needs-changes"] == 2
    assert m.labels_applied["security-risk"] == 1


def test_to_dict_is_json_serializable_shape():
    m = ReviewMetrics()
    m.record_review([_issue("info")])
    d = m.to_dict()
    assert isinstance(d["total_issues_by_severity"], dict)
    assert d["total_reviews"] == 1
