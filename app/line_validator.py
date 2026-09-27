"""
LineValidator — valide que les commentaires proposés par le LLM pointent
vers des lignes réellement présentes dans le diff (Bug 2 du cahier des
charges), avant de les poster via l'API GitHub Review Comments (AAR-21).

Action corrective attendue : "Croiser les numéros de lignes renvoyés par
l'IA avec la carte des lignes modifiées (hunks) du diff original. Si la
ligne est invalide, convertir le commentaire spécifique en un commentaire
global sur la PR." — c'est exactement ce que fait `validate_issues`.
"""

from dataclasses import dataclass

from .diff_parser import FileChange
from .llm.base import ReviewIssue


@dataclass
class ValidationResult:
    valid_issues: list[ReviewIssue]     # ligne confirmée dans le diff -> commentaire inline
    invalid_issues: list[ReviewIssue]   # ligne hors diff (Bug 2) -> à reconvertir en commentaire global


def validate_issues(issues: list[ReviewIssue], files: list[FileChange]) -> ValidationResult:
    """
    Sépare les issues renvoyées par le LLM en deux groupes, en croisant
    chaque (filename, line) avec les numéros de ligne réellement présents
    dans le diff du fichier concerné.
    """
    valid_lines_by_file = {f.filename: f.added_line_numbers() for f in files}

    valid: list[ReviewIssue] = []
    invalid: list[ReviewIssue] = []

    for issue in issues:
        allowed_lines = valid_lines_by_file.get(issue.filename)
        if allowed_lines is not None and issue.line in allowed_lines:
            valid.append(issue)
        else:
            invalid.append(issue)

    return ValidationResult(valid_issues=valid, invalid_issues=invalid)
