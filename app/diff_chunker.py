"""
AAR-19 : Découpage (chunking) du diff pour les grosses PR, afin d'éviter le
Bug 1 (dépassement de la limite de contexte du LLM, ex: 128k tokens).

Action corrective attendue par le cahier des charges : "Implémenter une
logique de découpage (chunking) du diff par fichier. Si un fichier est trop
grand, le tronquer [...] en avertissant l'utilisateur".

On utilise `tiktoken` (tokenizer d'OpenAI) comme estimation du nombre de
tokens — c'est une approximation raisonnable même pour Anthropic (les deux
tokenizers donnent des ordres de grandeur similaires), utilisée ici
uniquement pour dimensionner les chunks, pas pour un comptage exact facturé.
"""

from dataclasses import dataclass, field

from .diff_parser import FileChange, Hunk

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_ENCODER.encode(text))

except Exception:
    # tiktoken peut échouer soit parce qu'il n'est pas installé (ImportError),
    # soit parce que le téléchargement de son fichier d'encodage échoue
    # (erreur réseau) — dans les deux cas, on dégrade gracieusement plutôt
    # que de faire planter tout le pipeline de revue de code.
    def _count_tokens(text: str) -> int:
        # Approximation grossière (~4 caractères/token).
        return max(1, len(text) // 4)


@dataclass
class DiffChunk:
    files: list[FileChange]
    truncated_files: list[str] = field(default_factory=list)


def chunk_files(files: list[FileChange], max_tokens_per_chunk: int = 6000) -> list[DiffChunk]:
    """
    Regroupe les fichiers en chunks dont la taille cumulée reste sous
    `max_tokens_per_chunk`, afin que chaque appel au LLM reste dans sa
    limite de contexte. Si un seul fichier dépasse déjà ce budget à lui
    seul, il est tronqué (on garde ses premiers hunks) et signalé dans
    `truncated_files`.
    """
    chunks: list[DiffChunk] = []
    current_files: list[FileChange] = []
    current_truncated: list[str] = []
    current_tokens = 0

    for file in files:
        file_tokens = _count_tokens(_file_text(file))

        if file_tokens > max_tokens_per_chunk:
            file = _truncate_file(file, max_tokens_per_chunk)
            current_truncated = current_truncated + [file.filename]
            file_tokens = _count_tokens(_file_text(file))

        if current_files and current_tokens + file_tokens > max_tokens_per_chunk:
            chunks.append(DiffChunk(files=current_files, truncated_files=current_truncated))
            current_files, current_truncated, current_tokens = [], [], 0

        current_files.append(file)
        current_tokens += file_tokens

    if current_files:
        chunks.append(DiffChunk(files=current_files, truncated_files=current_truncated))

    return chunks


def _file_text(file: FileChange) -> str:
    return "\n".join(hunk.content for hunk in file.hunks)


def _truncate_file(file: FileChange, max_tokens: int) -> FileChange:
    """
    Ne garde que les premiers hunks du fichier jusqu'à atteindre le budget
    de tokens. Si un seul hunk dépasse déjà le budget restant à lui seul,
    il est tronqué ligne par ligne plutôt que d'être gardé intégralement
    (cas des gros fichiers générés en une seule fois, ex: refactoring massif).
    """
    kept_hunks: list[Hunk] = []
    running_tokens = 0

    for hunk in file.hunks:
        if running_tokens >= max_tokens:
            break  # budget déjà épuisé : on ignore les hunks suivants

        hunk_tokens = _count_tokens(hunk.content)

        if running_tokens + hunk_tokens <= max_tokens:
            kept_hunks.append(hunk)
            running_tokens += hunk_tokens
            continue

        # Ce hunk à lui seul dépasse le budget restant : troncature ligne par ligne
        remaining_budget = max_tokens - running_tokens
        truncated_hunk = _truncate_hunk(hunk, remaining_budget)
        if truncated_hunk.content:
            kept_hunks.append(truncated_hunk)
        break

    return FileChange(
        filename=file.filename,
        hunks=kept_hunks,
        lines_added=file.lines_added,
        lines_removed=file.lines_removed,
    )


def _truncate_hunk(hunk: Hunk, max_tokens: int) -> Hunk:
    """Tronque le contenu d'un hunk trop volumineux, ligne par ligne, jusqu'au budget donné."""
    lines = hunk.content.splitlines()
    kept_lines: list[str] = []
    running_tokens = 0

    for line in lines:
        line_tokens = _count_tokens(line)
        if running_tokens + line_tokens > max_tokens:
            break
        kept_lines.append(line)
        running_tokens += line_tokens

    content = "\n".join(kept_lines)
    if len(kept_lines) < len(lines):
        content += "\n# [... contenu tronqué par l'agent : fichier trop volumineux (Bug 1) ...]"

    return Hunk(header=hunk.header, new_start=hunk.new_start, content=content)
