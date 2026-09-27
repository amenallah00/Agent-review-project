"""
AAR-34 [RISQUE] Coûts API LLM — Gros diffs non maîtrisés.

Le chunking (AAR-19) résout le dépassement de la limite de CONTEXTE du LLM
(Bug 1), mais pas le risque de COÛT : une PR sous le seuil de lignes (US
4.2) mais touchant beaucoup de petits fichiers peut quand même générer un
grand nombre de chunks, donc un grand nombre d'appels API payants pour une
seule revue. Ce module plafonne le nombre de chunks réellement envoyés au
LLM par revue — au-delà, les fichiers restants sont signalés comme non
analysés plutôt que de générer un coût imprévu.
"""

from dataclasses import dataclass

from .diff_chunker import DiffChunk

DEFAULT_MAX_CHUNKS_PER_REVIEW = 8


@dataclass
class ChunkBudgetResult:
    chunks_to_process: list[DiffChunk]
    skipped_chunk_count: int
    skipped_file_names: list[str]


def apply_chunk_budget(chunks: list[DiffChunk], max_chunks: int = DEFAULT_MAX_CHUNKS_PER_REVIEW) -> ChunkBudgetResult:
    """
    Ne garde que les `max_chunks` premiers chunks (déjà dans l'ordre des
    fichiers du diff, cf. diff_chunker.chunk_files). Les fichiers des
    chunks au-delà du plafond sont listés pour être signalés dans le
    résumé de la revue — jamais silencieusement ignorés.
    """
    if len(chunks) <= max_chunks:
        return ChunkBudgetResult(chunks_to_process=chunks, skipped_chunk_count=0, skipped_file_names=[])

    kept = chunks[:max_chunks]
    skipped = chunks[max_chunks:]
    skipped_files = [f.filename for chunk in skipped for f in chunk.files]

    return ChunkBudgetResult(
        chunks_to_process=kept,
        skipped_chunk_count=len(skipped),
        skipped_file_names=skipped_files,
    )
