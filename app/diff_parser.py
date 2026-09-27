"""
AAR-14 : Parsing du diff d'une Pull Request (US 2.1).

Transforme le texte brut d'un diff unifié (format renvoyé par l'API GitHub
avec Accept: application/vnd.github.v3.diff) en une liste structurée de
FileChange, chacun avec ses hunks. On calcule aussi l'ensemble des numéros
de ligne réellement couverts par le diff (`added_line_numbers`) : c'est ce
qui permettra, dans un ticket ultérieur, de détecter le Bug 2 (l'IA propose
un commentaire sur une ligne hors diff) avant même d'appeler l'API GitHub.
"""

import re
from dataclasses import dataclass, field

# US 2.1 : fichiers non pertinents à ignorer avant l'envoi au LLM
IGNORED_FILE_PATTERNS = [
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"composer\.lock$",
    r"\.(png|jpe?g|gif|svg|ico|webp|bmp)$",
    r"\.(woff2?|ttf|eot)$",
    r"^dist/",
    r"^build/",
    r"\.min\.(js|css)$",
]

_FILE_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    header: str
    new_start: int
    content: str


@dataclass
class FileChange:
    filename: str
    hunks: list[Hunk] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0

    def added_line_numbers(self) -> set[int]:
        """
        Numéros de ligne (côté fichier après modification) qui font
        partie du diff — sert à valider qu'un commentaire de l'IA
        pointe bien vers une ligne réellement modifiée (Bug 2).
        """
        return set(self.added_lines_with_content().keys())

    def added_lines_with_content(self) -> dict[int, str]:
        """
        AAR-16 : dict {numéro_de_ligne: contenu} pour les lignes réellement
        ajoutées par cette PR — sert à la détection de patterns problématiques
        sans avoir à re-analyser tout le fichier.
        """
        result: dict[int, str] = {}
        for hunk in self.hunks:
            result.update(_expand_hunk_line_contents(hunk))
        return result


def parse_diff(raw_diff: str) -> list[FileChange]:
    """Parse un diff unifié brut en une liste de FileChange avec leurs hunks."""
    files: list[FileChange] = []
    current_file: FileChange | None = None
    current_hunk_header: str | None = None
    current_hunk_lines: list[str] = []

    def flush_hunk() -> None:
        nonlocal current_hunk_header, current_hunk_lines
        if current_file is not None and current_hunk_header is not None:
            match = _HUNK_HEADER_RE.match(current_hunk_header)
            new_start = int(match.group(2)) if match else 0
            current_file.hunks.append(
                Hunk(
                    header=current_hunk_header,
                    new_start=new_start,
                    content="\n".join(current_hunk_lines),
                )
            )
        current_hunk_header = None
        current_hunk_lines = []

    for line in raw_diff.splitlines():
        file_match = _FILE_HEADER_RE.match(line)
        if file_match:
            flush_hunk()
            if current_file is not None:
                files.append(current_file)
            current_file = FileChange(filename=file_match.group(2))
            continue

        if line.startswith("@@"):
            flush_hunk()
            current_hunk_header = line
            continue

        if current_file is not None and current_hunk_header is not None:
            current_hunk_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                current_file.lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_file.lines_removed += 1

    flush_hunk()
    if current_file is not None:
        files.append(current_file)

    return files


def _expand_hunk_line_contents(hunk: Hunk) -> dict[int, str]:
    """Calcule {numéro_de_ligne: contenu} pour les lignes ajoutées d'un hunk."""
    result: dict[int, str] = {}
    current_line = hunk.new_start
    for line in hunk.content.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            result[current_line] = line[1:]
            current_line += 1
        elif line.startswith(" "):
            current_line += 1
        # les lignes '-' n'existent pas dans le nouveau fichier : pas d'incrément
    return result


def filter_irrelevant_files(files: list[FileChange]) -> list[FileChange]:
    """
    US 2.1 : retire les fichiers non pertinents (lockfiles, images, builds).
    AAR-35 [RISQUE] : retire aussi les fichiers manifestement sensibles
    (clés privées, .env...) — ceux-ci ne doivent jamais atteindre le LLM,
    même sous forme de diff.
    """
    from .secret_redactor import is_sensitive_file

    patterns = [re.compile(p) for p in IGNORED_FILE_PATTERNS]
    return [
        f for f in files
        if not any(p.search(f.filename) for p in patterns)
        and not is_sensitive_file(f.filename)
    ]


def total_lines_changed(files: list[FileChange]) -> int:
    """Utilisé par le garde-fou de taille de PR (US 4.2)."""
    return sum(f.lines_added + f.lines_removed for f in files)
