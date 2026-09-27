from app.linter import LintIssue
from app.local_findings import lint_issues_to_review_issues, pattern_matches_to_review_issues
from app.pattern_detector import PatternMatch


def test_lint_issues_are_converted_with_high_confidence():
    issues = lint_issues_to_review_issues([
        LintIssue(filename="a.py", line=3, severity="error", message="Undefined variable", rule="undefined-variable"),
        LintIssue(filename="a.py", line=5, severity="convention", message="Missing docstring", rule="missing-module-docstring"),
    ])
    assert len(issues) == 2
    assert issues[0].severity == "critical"
    assert issues[0].confidence == "high"
    assert "[Linter/undefined-variable]" in issues[0].message
    assert issues[1].severity == "info"


def test_pattern_matches_are_converted_with_high_confidence():
    issues = pattern_matches_to_review_issues([
        PatternMatch(filename="a.py", line=1, pattern_name="eval_usage",
                     message="Usage de eval() détecté", severity="critical"),
    ])
    assert len(issues) == 1
    assert issues[0].severity == "critical"
    assert issues[0].confidence == "high"
    assert "[Pattern/eval_usage]" in issues[0].message
