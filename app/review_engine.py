"""
ReviewEngine (diagramme de classes) : orchestre linter (AAR-15), détection
de patterns (AAR-16), chunking (AAR-19), plafond de coûts (AAR-34), appel
LLM (AAR-17/18), filtre anti-hallucination (AAR-33) et filtrage (AAR-20)
pour produire la liste finale de commentaires prêts à être publiés.

La publication effective sur GitHub (US 3.1) est faite par
`review_publisher.publish_review`, à partir du `ReviewOutcome` renvoyé ici.
"""

import logging
from dataclasses import dataclass, field

from .comment_filter import filter_and_prioritize
from .config import settings
from .cost_guard import apply_chunk_budget
from .diff_chunker import chunk_files
from .diff_parser import FileChange
from .github_app import GitHubClient
from .hallucination_guard import filter_hallucinations
from .linter import lint_file
from .llm.anthropic_provider import AnthropicProvider
from .llm.azure_openai_provider import AzureOpenAIProvider
from .llm.base import LLMProvider, ReviewIssue
from .llm.openai_provider import OpenAIProvider
from .local_findings import lint_issues_to_review_issues, pattern_matches_to_review_issues
from .pattern_detector import detect_patterns
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("agent-review.review_engine")


@dataclass
class ReviewOutcome:
    issues: list[ReviewIssue] = field(default_factory=list)
    llm_summaries: list[str] = field(default_factory=list)
    truncated_files: list[str] = field(default_factory=list)      # Bug 1 : fichiers tronqués (contexte)
    cost_skipped_files: list[str] = field(default_factory=list)   # AAR-34 : fichiers non analysés (budget de coût)
    flagged_issues_count: int = 0                                  # AAR-33 : issues écartées (hallucination probable)
    llm_failed: bool = False                                       # True si l'appel LLM a échoué sur au moins un chunk


def get_llm_provider() -> LLMProvider:
    """Sélectionne le fournisseur LLM configuré : OpenAI direct, Anthropic, ou Azure OpenAI Service."""
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )
    return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)


async def review_pull_request(
    client: GitHubClient,
    owner: str,
    repo: str,
    head_sha: str,
    files: list[FileChange],
) -> ReviewOutcome:
    """
    Exécute le pipeline complet de revue sur les fichiers déjà extraits et
    filtrés par AAR-14, et renvoie un `ReviewOutcome` prêt pour AAR-23.

    ⚠️ Un échec de l'appel LLM (rate limit, panne, facturation...) ne fait
    JAMAIS planter cette fonction : les découvertes locales déterministes
    (linter + patterns critiques) sont toujours incluses dans le résultat,
    et le pipeline continue avec les chunks suivants.
    """
    llm = get_llm_provider()
    all_issues: list[ReviewIssue] = []
    llm_summaries: list[str] = []
    all_truncated_files: list[str] = []
    llm_failed = False

    chunks = chunk_files(files)

    # AAR-34 [RISQUE] : plafonne le nombre de chunks (donc d'appels LLM payants) par revue
    budget = apply_chunk_budget(chunks, max_chunks=settings.max_chunks_per_review)
    if budget.skipped_chunk_count:
        logger.warning(
            "AAR-34 : %d chunk(s) non analysé(s) (plafond de coût atteint), fichiers concernés : %s",
            budget.skipped_chunk_count, ", ".join(budget.skipped_file_names),
        )

    logger.info(
        "Diff découpé en %d chunk(s) pour %d fichier(s) (%d traité(s) après plafond de coût)",
        len(chunks), len(files), len(budget.chunks_to_process),
    )

    for chunk_index, chunk in enumerate(budget.chunks_to_process):
        if chunk.truncated_files:
            logger.warning(
                "Chunk %d : fichier(s) tronqué(s) (Bug 1) : %s",
                chunk_index, ", ".join(chunk.truncated_files),
            )
            all_truncated_files.extend(chunk.truncated_files)

        lint_issues = []
        pattern_matches = []

        for file in chunk.files:
            try:
                content = await client.get_file_content(owner, repo, file.filename, ref=head_sha)
            except Exception:
                logger.exception("Impossible de récupérer le contenu de %s, linter ignoré pour ce fichier", file.filename)
                content = None

            if content is not None:
                lint_issues += lint_file(file.filename, content)
            pattern_matches += detect_patterns(file.filename, file.added_lines_with_content())

        # Les découvertes déterministes (linter + patterns critiques) sont
        # TOUJOURS ajoutées, indépendamment du succès de l'appel LLM ci-dessous.
        all_issues.extend(lint_issues_to_review_issues(lint_issues))
        all_issues.extend(pattern_matches_to_review_issues(pattern_matches))

        try:
            user_prompt = build_user_prompt(chunk.files, lint_issues, pattern_matches)
            result = await llm.analyze(SYSTEM_PROMPT, user_prompt)
            all_issues.extend(result.issues)
            if result.summary:
                llm_summaries.append(result.summary)
        except Exception as exc:
            llm_failed = True
            logger.exception(
                "Chunk %d : échec de l'appel LLM (%s) — la revue continue avec les détections locales uniquement",
                chunk_index, type(exc).__name__,
            )

    # AAR-33 [RISQUE] : écarte les issues à faible confiance ou non ancrées dans le code réel
    line_contents = {
        (f.filename, line): content
        for f in files
        for line, content in f.added_lines_with_content().items()
    }
    hallucination_check = filter_hallucinations(all_issues, line_contents, min_confidence=settings.min_issue_confidence)
    if hallucination_check.flagged_issues:
        logger.warning(
            "AAR-33 : %d issue(s) écartée(s) (confiance faible ou non ancrée dans le code)",
            len(hallucination_check.flagged_issues),
        )

    final_issues = filter_and_prioritize(hallucination_check.trusted_issues, max_comments=settings.max_comments_per_review)
    logger.info(
        "Revue terminée : %d issue(s) brute(s) -> %d après anti-hallucination -> %d après filtrage/priorisation",
        len(all_issues), len(hallucination_check.trusted_issues), len(final_issues),
    )
    if llm_failed:
        llm_summaries.append(
            "⚠️ L'appel au LLM a échoué pour au moins une partie du diff — "
            "cette revue ne contient que les détections locales (linter + patterns)."
        )

    return ReviewOutcome(
        issues=final_issues,
        llm_summaries=llm_summaries,
        truncated_files=all_truncated_files,
        cost_skipped_files=budget.skipped_file_names,
        flagged_issues_count=len(hallucination_check.flagged_issues),
        llm_failed=llm_failed,
    )
