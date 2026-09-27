"""
AAR-16 : Détection de patterns de code problématiques par heuristiques
(regex). Complète le linter (AAR-15) et le LLM (AAR-18) par des vérifications
rapides, déterministes et gratuites (pas d'appel API nécessaire) — utile
notamment pour les problèmes de sécurité "évidents" mentionnés dans le
périmètre du cahier des charges ("détection des problèmes de sécurité de
base").

On analyse uniquement les LIGNES AJOUTÉES du diff (pas tout le fichier),
pour ne signaler que du code réellement introduit par cette PR.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatternMatch:
    filename: str
    line: int
    pattern_name: str
    message: str
    severity: str  # "critical" | "warning" | "info"


@dataclass
class _Pattern:
    name: str
    regex: re.Pattern
    message: str
    severity: str
    file_extensions: set[str] | None = None  # None = tous les fichiers texte


_PATTERNS: list[_Pattern] = [
    _Pattern(
        name="eval_usage",
        regex=re.compile(r"\beval\s*\("),
        message="Usage de eval() détecté : risque d'exécution de code arbitraire.",
        severity="critical",
    ),
    _Pattern(
        name="hardcoded_secret",
        regex=re.compile(
            r"(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{8,}[\"']",
            re.IGNORECASE,
        ),
        message="Valeur ressemblant à un secret codé en dur (clé API, mot de passe...).",
        severity="critical",
    ),
    _Pattern(
        name="sql_string_concat",
        regex=re.compile(r"(SELECT|INSERT|UPDATE|DELETE)\b.{0,80}[\"']\s*\+", re.IGNORECASE),
        message="Concaténation de chaîne dans une requête SQL : risque d'injection SQL.",
        severity="critical",
    ),
    _Pattern(
        name="bare_except",
        regex=re.compile(r"^\s*except\s*:\s*$"),
        message="`except:` nu : capture toutes les exceptions, y compris SystemExit/KeyboardInterrupt.",
        severity="warning",
        file_extensions={".py"},
    ),
    _Pattern(
        name="debug_print_left_in",
        regex=re.compile(r"^\s*(print\(|console\.log\()"),
        message="Instruction de debug (print/console.log) probablement oubliée.",
        severity="info",
    ),
    _Pattern(
        name="loose_equality_js",
        regex=re.compile(r"[^=!]==[^=]"),
        message="Utilisation de == au lieu de === (comparaison non stricte en JS/TS).",
        severity="warning",
        file_extensions={".js", ".jsx", ".ts", ".tsx"},
    ),
]


def detect_patterns(filename: str, added_lines: dict[int, str]) -> list[PatternMatch]:
    """
    `added_lines` : dict {numéro_de_ligne: contenu_de_la_ligne}, tel que
    renvoyé par `FileChange.added_lines_with_content()` (AAR-14).
    """
    suffix = Path(filename).suffix.lower()
    matches: list[PatternMatch] = []

    for pattern in _PATTERNS:
        if pattern.file_extensions and suffix not in pattern.file_extensions:
            continue
        for line_number, line_content in added_lines.items():
            if pattern.regex.search(line_content):
                matches.append(
                    PatternMatch(
                        filename=filename,
                        line=line_number,
                        pattern_name=pattern.name,
                        message=pattern.message,
                        severity=pattern.severity,
                    )
                )
    return matches
