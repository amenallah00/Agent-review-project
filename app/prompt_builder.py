"""
AAR-17 : Construction du prompt système et du prompt utilisateur pour la
revue de code (US 2.2), en intégrant le contexte du linter (AAR-15) et des
patterns détectés (AAR-16) pour aider le LLM à être plus précis et réduire
les faux négatifs.
"""

from .diff_parser import FileChange
from .linter import LintIssue
from .pattern_detector import PatternMatch
from .secret_redactor import redact_secrets

SYSTEM_PROMPT = """Tu es un développeur senior expert, spécialisé en revue de code, sécurité et bonnes pratiques.
Tu analyses uniquement le code fourni (issu d'un diff de Pull Request), pas le reste du dépôt.

Réponds STRICTEMENT en JSON, selon ce schéma exact, sans aucun texte hors du JSON :
{
  "summary": "résumé global en 1-2 phrases",
  "issues": [
    {
      "filename": "chemin/du/fichier.py",
      "line": 42,
      "severity": "critical" | "warning" | "info",
      "confidence": "high" | "medium" | "low",
      "message": "description claire et actionnable du problème, citant le nom de variable/fonction concerné entre backticks (`nom`) quand pertinent",
      "suggestion": "code de remplacement suggéré, ou null si non applicable"
    }
  ]
}

Règles impératives :
- N'invente JAMAIS de numéro de ligne : utilise uniquement les numéros de ligne indiqués dans le diff fourni (préfixés "L<numéro>:").
- "confidence" reflète ta certitude que ce problème est RÉEL, pas une supposition : si tu hésites, mets "low" plutôt que d'affirmer avec assurance quelque chose d'incertain.
- Si tu cites un nom de variable, fonction ou valeur entre backticks, il doit apparaître EXACTEMENT dans le code fourni — n'invente jamais un identifiant qui n'existe pas dans le diff.
- Priorise les problèmes de sécurité et les bugs réels avant le style.
- Si un avertissement du linter ou un pattern détecté automatiquement est fourni, tiens-en compte mais ne le recopie pas
  tel quel : reformule et évalue s'il est réellement pertinent dans son contexte.
- Si aucun problème n'est trouvé, renvoie une liste "issues" vide.
"""


def build_user_prompt(
    files: list[FileChange],
    lint_issues: list[LintIssue],
    pattern_matches: list[PatternMatch],
) -> str:
    """Assemble le diff (avec numéros de ligne explicites), les résultats du
    linter et les patterns détectés en un seul prompt utilisateur."""
    sections = ["## Fichiers modifiés (lignes ajoutées, avec leur numéro réel)\n"]

    for file in files:
        sections.append(f"### {file.filename}")
        added = file.added_lines_with_content()
        if not added:
            sections.append("(aucune ligne ajoutée détectée, uniquement des suppressions)")
            continue
        for line_number in sorted(added):
            # AAR-35 [RISQUE] : ne jamais envoyer la valeur réelle d'un secret au LLM.
            safe_content = redact_secrets(added[line_number])
            sections.append(f"L{line_number}: {safe_content}")

    if lint_issues:
        sections.append("\n## Avertissements du linter statique (Pylint/ESLint)")
        for issue in lint_issues:
            sections.append(
                f"- [{issue.severity}] {issue.filename}:{issue.line} ({issue.rule}) — {issue.message}"
            )

    if pattern_matches:
        sections.append("\n## Patterns problématiques détectés automatiquement")
        for match in pattern_matches:
            sections.append(f"- [{match.severity}] {match.filename}:{match.line} — {match.message}")

    sections.append(
        "\n## Instruction\nAnalyse ce code modifié et renvoie ton évaluation au format JSON "
        "défini dans le prompt système. Utilise exclusivement les numéros de ligne 'L<numéro>' listés ci-dessus."
    )

    return "\n".join(sections)
