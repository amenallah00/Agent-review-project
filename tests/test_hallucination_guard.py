from app.hallucination_guard import filter_hallucinations, is_grounded
from app.llm.base import ReviewIssue


def _issue(message, confidence="medium", line=10, filename="app.py"):
    return ReviewIssue(filename=filename, line=line, severity="warning", message=message, confidence=confidence)


def test_is_grounded_true_when_no_backtick_identifiers():
    issue = _issue("Cette fonction pourrait être simplifiée.")
    assert is_grounded(issue, "def foo(): pass") is True


def test_is_grounded_true_when_identifier_present_in_line():
    issue = _issue("La variable `user_id` n'est pas validée.")
    assert is_grounded(issue, "query(user_id)") is True


def test_is_grounded_false_when_identifier_absent_from_line():
    issue = _issue("La fonction `does_not_exist` cause un problème.")
    assert is_grounded(issue, "x = 1 + 2") is False


def test_is_grounded_true_when_line_content_unknown():
    """Pas de contenu de ligne disponible (ex: commentaire déjà global) : on ne pénalise pas."""
    issue = _issue("Problème avec `something`.")
    assert is_grounded(issue, None) is True


def test_filter_hallucinations_keeps_high_confidence_grounded_issue():
    issue = _issue("La variable `x` est mal utilisée.", confidence="high")
    line_contents = {("app.py", 10): "x = compute()"}
    result = filter_hallucinations([issue], line_contents, min_confidence="medium")
    assert issue in result.trusted_issues
    assert result.flagged_issues == []


def test_filter_hallucinations_flags_low_confidence_issue():
    issue = _issue("Peut-être un problème ici.", confidence="low")
    line_contents = {("app.py", 10): "x = compute()"}
    result = filter_hallucinations([issue], line_contents, min_confidence="medium")
    assert issue in result.flagged_issues
    assert result.trusted_issues == []


def test_filter_hallucinations_flags_ungrounded_issue_even_with_high_confidence():
    issue = _issue("La fonction `phantom_func` est dangereuse.", confidence="high")
    line_contents = {("app.py", 10): "x = compute()"}
    result = filter_hallucinations([issue], line_contents, min_confidence="medium")
    assert issue in result.flagged_issues


def test_filter_hallucinations_separates_mixed_batch():
    trusted_issue = _issue("La variable `x` est mal utilisée.", confidence="high", line=10)
    flagged_issue = _issue("faible confiance", confidence="low", line=11)
    line_contents = {("app.py", 10): "x = compute()", ("app.py", 11): "y = 2"}

    result = filter_hallucinations([trusted_issue, flagged_issue], line_contents)
    assert result.trusted_issues == [trusted_issue]
    assert result.flagged_issues == [flagged_issue]
