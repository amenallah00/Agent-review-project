from app.diff_parser import FileChange, Hunk
from app.line_validator import validate_issues
from app.llm.base import ReviewIssue


def _file_with_added_lines(filename: str, *line_numbers: int) -> FileChange:
    """Fabrique un FileChange minimal dont added_line_numbers() renvoie exactement ces lignes."""
    max_line = max(line_numbers)
    content_lines = []
    for i in range(1, max_line + 1):
        content_lines.append(f"+line {i}" if i in line_numbers else f" line {i}")
    hunk = Hunk(header="@@ -1,1 +1,%d @@" % max_line, new_start=1, content="\n".join(content_lines))
    return FileChange(filename=filename, hunks=[hunk])


def test_issue_on_valid_line_is_kept():
    files = [_file_with_added_lines("app/main.py", 10, 11)]
    issues = [ReviewIssue(filename="app/main.py", line=10, severity="warning", message="ok")]

    result = validate_issues(issues, files)
    assert len(result.valid_issues) == 1
    assert len(result.invalid_issues) == 0


def test_issue_on_line_outside_diff_is_flagged_invalid():
    files = [_file_with_added_lines("app/main.py", 10, 11)]
    issues = [ReviewIssue(filename="app/main.py", line=999, severity="warning", message="ligne inexistante")]

    result = validate_issues(issues, files)
    assert len(result.valid_issues) == 0
    assert len(result.invalid_issues) == 1


def test_issue_on_unknown_file_is_flagged_invalid():
    files = [_file_with_added_lines("app/main.py", 10)]
    issues = [ReviewIssue(filename="app/other.py", line=10, severity="info", message="fichier absent du diff")]

    result = validate_issues(issues, files)
    assert len(result.invalid_issues) == 1


def test_mixed_valid_and_invalid_issues():
    files = [_file_with_added_lines("app/main.py", 5, 6, 7)]
    issues = [
        ReviewIssue(filename="app/main.py", line=5, severity="critical", message="valide"),
        ReviewIssue(filename="app/main.py", line=42, severity="warning", message="invalide"),
    ]

    result = validate_issues(issues, files)
    assert len(result.valid_issues) == 1
    assert len(result.invalid_issues) == 1
    assert result.valid_issues[0].message == "valide"
    assert result.invalid_issues[0].message == "invalide"
