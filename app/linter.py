"""
AAR-15 : Intégration d'un linter statique (Pylint pour Python, ESLint pour JS/TS).

Le linter s'exécute sur le contenu COMPLET du fichier (récupéré via l'API
GitHub, pas seulement le diff), car un linter a besoin d'un fichier
syntaxiquement analysable dans son ensemble pour donner des résultats fiables.
Ses résultats viendront enrichir le contexte envoyé au LLM (AAR-17).
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PYTHON_EXTENSIONS = {".py"}
JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


@dataclass
class LintIssue:
    filename: str
    line: int
    severity: str  # "error" | "warning" | "convention" | "refactor"
    message: str
    rule: str


def lint_file(filename: str, content: str) -> list[LintIssue]:
    """
    Écrit le contenu dans un fichier temporaire portant le bon nom/extension,
    puis exécute le linter adapté au langage détecté. Retourne une liste vide
    (sans jamais lever d'exception) si le langage n'est pas supporté ou si
    l'outil n'est pas installé sur cet environnement — le linter est un
    enrichissement, sa panne ne doit jamais bloquer la revue de code.
    """
    suffix = Path(filename).suffix.lower()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / Path(filename).name
        tmp_path.write_text(content, encoding="utf-8")

        if suffix in PYTHON_EXTENSIONS:
            return _run_pylint(tmp_path)
        if suffix in JS_TS_EXTENSIONS:
            return _run_eslint(tmp_path)
        return []


def _run_pylint(filepath: Path) -> list[LintIssue]:
    try:
        result = subprocess.run(
            ["pylint", "--output-format=json", str(filepath)],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if not result.stdout.strip():
        return []

    try:
        raw_issues = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    severity_map = {"error": "error", "fatal": "error", "warning": "warning",
                     "convention": "convention", "refactor": "refactor"}

    return [
        LintIssue(
            filename=filepath.name,
            line=issue.get("line", 0),
            severity=severity_map.get(issue.get("type", ""), "warning"),
            message=issue.get("message", ""),
            rule=issue.get("symbol") or issue.get("message-id", ""),
        )
        for issue in raw_issues
    ]


def _run_eslint(filepath: Path) -> list[LintIssue]:
    try:
        result = subprocess.run(
            ["npx", "--yes", "eslint", "--no-eslintrc", "--env", "es2021,node,browser",
             "--parser-options=ecmaVersion:2021", "--format=json", str(filepath)],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if not result.stdout.strip():
        return []

    try:
        raw_files = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    issues: list[LintIssue] = []
    for file_result in raw_files:
        for msg in file_result.get("messages", []):
            issues.append(
                LintIssue(
                    filename=filepath.name,
                    line=msg.get("line", 0),
                    severity="error" if msg.get("severity") == 2 else "warning",
                    message=msg.get("message", ""),
                    rule=msg.get("ruleId") or "",
                )
            )
    return issues
