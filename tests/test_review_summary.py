from app.llm.base import ReviewIssue
from app.review_summary import build_review_summary


def test_summary_includes_llm_text_and_counts():
    issues = [
        ReviewIssue(filename="a.py", line=1, severity="critical", message="injection SQL"),
        ReviewIssue(filename="a.py", line=2, severity="warning", message="style"),
    ]
    summary = build_review_summary(
        llm_summaries=["Le code présente une vulnérabilité critique."],
        all_issues=issues,
        global_issues=[],
        truncated_files=[],
    )
    assert "Le code présente une vulnérabilité critique." in summary
    assert "Critique : 1" in summary
    assert "Avertissement : 1" in summary


def test_summary_reports_clean_code_when_no_issues():
    summary = build_review_summary(llm_summaries=["Rien à signaler."], all_issues=[], global_issues=[], truncated_files=[])
    assert "Aucun problème détecté" in summary


def test_summary_mentions_truncated_files():
    summary = build_review_summary(
        llm_summaries=[], all_issues=[], global_issues=[], truncated_files=["huge_refactor.py"]
    )
    assert "huge_refactor.py" in summary
    assert "Bug 1" in summary


def test_summary_lists_global_issues_separately():
    global_issue = ReviewIssue(filename="a.py", line=999, severity="warning", message="ligne hors diff")
    summary = build_review_summary(
        llm_summaries=[], all_issues=[global_issue], global_issues=[global_issue], truncated_files=[]
    )
    assert "Commentaires additionnels" in summary
    assert "ligne hors diff" in summary


def test_summary_mentions_cost_skipped_files():
    summary = build_review_summary(
        llm_summaries=[], all_issues=[], global_issues=[], truncated_files=[],
        cost_skipped_files=["module_a.py", "module_b.py"],
    )
    assert "module_a.py" in summary
    assert "plafond de coût" in summary


def test_summary_mentions_flagged_issues_count():
    summary = build_review_summary(
        llm_summaries=[], all_issues=[], global_issues=[], truncated_files=[],
        flagged_issues_count=3,
    )
    assert "3 observation" in summary
    assert "anti-hallucination" in summary


def test_summary_omits_optional_sections_when_not_provided():
    summary = build_review_summary(llm_summaries=["ok"], all_issues=[], global_issues=[], truncated_files=[])
    assert "plafond de coût" not in summary
    assert "anti-hallucination" not in summary
