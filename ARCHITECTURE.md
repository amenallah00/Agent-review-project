# Architecture — Agent IA de Revue de Code (AAR-1)

Ce document résume l'architecture retenue, cohérente avec les diagrammes UML
du projet (diagramme de classes notamment).

## Vue d'ensemble

```
GitHub (webhooks) --> app/main.py (FastAPI, endpoint /webhook)
                            |
                            v
                    app/security.py       (AAR-13 : vérifie la signature HMAC)
                            |
                            v
                    app/bot_guard.py      (Bug 3 : anti-boucle)
                            |
                            v
                    app/github_app.py     (AAR-11 : JWT App -> token d'installation)
                            |
                            v
                    app/diff_parser.py    (AAR-14 : parse + filtre le diff, US 2.1)
                            |
                            v
              [à venir] app/llm/*         (US 2.2 : appel OpenAI/Anthropic)
                            |
                            v
              [à venir] app/line_validator.py  (Bug 2 : validation des lignes)
                            |
                            v
                    app/github_app.py     (US 3.1 : create_review / post_issue_comment)
```

## Correspondance avec le diagramme de classes

| Classe (diagramme UML) | Fichier / fonction correspondant |
|---|---|
| `WebhookServer` | `app/main.py` (`webhook_receiver`, `handle_pull_request_event`) |
| `BotGuard` | `app/bot_guard.py` |
| `DiffExtractor` | `GitHubClient.get_diff` + `diff_parser.parse_diff` |
| `FileFilter` | `diff_parser.filter_irrelevant_files` |
| `SizeGuard` | `diff_parser.total_lines_changed` + vérification dans `handle_pull_request_event` |
| `GitHubClient` | `app/github_app.py` (classe `GitHubClient`, + `get_file_content` pour le linter) |
| `FileChange` | `diff_parser.FileChange` (dataclass) |
| `DiffChunker` | `app/diff_chunker.py` (AAR-19, Bug 1) |
| *(linter statique, non présent dans le diagramme initial)* | `app/linter.py` (AAR-15 : Pylint / ESLint) |
| *(détection de patterns, non présent dans le diagramme initial)* | `app/pattern_detector.py` (AAR-16) |
| `ReviewEngine` | `app/review_engine.py` (orchestrateur, AAR-17/18/19/20) |
| `LLMProvider`, `AzureOpenAIService`/`OpenAIService`, `AnthropicService` | `app/llm/base.py`, `app/llm/openai_provider.py`, `app/llm/anthropic_provider.py` (AAR-18) |
| *(construction du prompt)* | `app/prompt_builder.py` (AAR-17) |
| *(filtrage/priorisation)* | `app/comment_filter.py` (AAR-20) |
| `LineValidator`, `CommandHandler` | **à implémenter dans les tickets des sprints suivants** (Bug 2, US 3.1, US 3.2) |

## Sprint 2 — Analyse statique & Revue par LLM (AAR-15 à AAR-20)

Pipeline complet désormais opérationnel dans `review_engine.review_pull_request()` :

```
files (AAR-14, déjà filtrés)
      |
      v
diff_chunker.chunk_files()          (AAR-19 : découpe/tronque si trop volumineux, Bug 1)
      |
      v (pour chaque chunk)
  linter.lint_file()                (AAR-15 : Pylint pour .py, ESLint pour .js/.ts/.jsx/.tsx)
  pattern_detector.detect_patterns() (AAR-16 : eval(), secrets en dur, injection SQL, etc.)
      |
      v
prompt_builder.build_user_prompt()  (AAR-17 : assemble diff + lint + patterns)
      |
      v
llm.analyze()                       (AAR-18 : appel OpenAI GPT-4o ou Anthropic Claude 3.5 Sonnet)
      |
      v
comment_filter.filter_and_prioritize()  (AAR-20 : dédoublonnage, tri par sévérité, plafond)
      |
      v
liste finale de ReviewIssue, prête pour la publication (US 3.1, ticket ultérieur)
```

**Notes d'implémentation :**
- Le linter dégrade gracieusement (`[]`) si l'outil n'est pas installé ou plante — jamais bloquant pour la revue.
- ESLint nécessite Node.js/npm installés dans l'environnement d'exécution (voir `README.md`) ; Pylint est inclus dans `requirements.txt`.
- Le chunking utilise `tiktoken` comme estimation du nombre de tokens (approximation valable pour les deux fournisseurs), avec repli automatique sur une estimation par caractères si `tiktoken` est indisponible (pas de réseau, pas installé).
- Le comptage de tokens sert uniquement à dimensionner les chunks, pas de facturation exacte.

## Sprint 3 — Tickets de risque (AAR-32, AAR-35)

### AAR-32 [RISQUE] Rate limiting GitHub API — Trop de commentaires

Deux mécanismes complémentaires :
1. **AAR-20** limite déjà le *nombre* de commentaires envoyés par revue (`MAX_COMMENTS_PER_REVIEW`, configurable via `.env`, 15 par défaut).
2. **`app/rate_limit.py`** gère les réponses HTTP de GitHub qui indiquent un dépassement de débit :
   - `429` (rate limit classique)
   - `403` avec `X-RateLimit-Remaining: 0`, ou corps mentionnant une "secondary rate limit" (limite anti-abus, qui peut se déclencher même sans avoir épuisé le quota horaire — typiquement en cas de créations de commentaires trop rapprochées).

   Retry avec backoff (respecte l'en-tête `Retry-After` si fourni, sinon 1s/2s/4s), branché sur `create_review()` et `post_issue_comment()` dans `github_app.py` — les deux appels d'écriture les plus exposés à ce risque.

### AAR-35 [RISQUE] Sécurité — Exposition du code source au LLM

Deux mécanismes complémentaires, dans `app/secret_redactor.py` :
1. **Exclusion complète** de certains fichiers avant même l'extraction du diff (`.env`, `.pem`, `.key`, `id_rsa`, `credentials.json`...) — branchée directement dans `diff_parser.filter_irrelevant_files()`, donc appliquée automatiquement dès AAR-14.
2. **Rédaction des valeurs de secrets** (`redact_secrets()`) dans le texte réellement inclus au prompt LLM (`prompt_builder.py`) — la ligne `api_key = "sk-abc123..."` devient `api_key = "[REDACTED]"` avant d'être envoyée à OpenAI/Anthropic. Le nom de la variable reste visible (utile pour le contexte de l'analyse), jamais sa valeur.

**Important :** la détection de patterns (AAR-16, `pattern_detector.py`) continue d'analyser le contenu **non rédigé**, sinon elle ne pourrait plus détecter les secrets codés en dur — la rédaction n'intervient qu'au moment de construire le prompt destiné à sortir vers OpenAI/Anthropic, pas avant.

## Sprint 4 — Publication de la revue (AAR-21, AAR-22, AAR-23)

Le pipeline est désormais complet de bout en bout : `main.py` appelle
`review_engine.review_pull_request()` (renvoie un `ReviewOutcome`), puis
`review_publisher.publish_review()` qui assemble tout et poste réellement
sur GitHub via `GitHubClient.create_review()`.

```
ReviewOutcome (issues, résumés LLM, fichiers tronqués)
        |
        v
line_validator.validate_issues()      (Bug 2 : ligne dans le diff ? oui/non)
   |                        |
   v (oui)                  v (non)
inline_comments      global_issues (reconvertis)
   |                        |
   v                        v
suggestion_formatter    review_summary.build_review_summary()
.format_comment_body()  (résumé LLM + décompte + fichiers tronqués + issues globales)
   |                        |
   +------------+-----------+
                v
   GitHubClient.create_review(comments=[...], body=résumé)
```

- **AAR-21** (`review_publisher.py` + `line_validator.py`) : c'est ici que le **Bug 2** est enfin traité concrètement — une issue dont la ligne n'existe pas dans le diff n'est **jamais** envoyée comme commentaire inline (ce qui provoquerait une erreur 422 de l'API GitHub), elle est automatiquement basculée dans le résumé global.
- **AAR-22** (`suggestion_formatter.py`) : ajoute un bloc ` ```suggestion ` Markdown quand le LLM fournit un remplacement de code, pour que le développeur puisse l'appliquer en un clic depuis GitHub.
- **AAR-23** (`review_summary.py`) : construit le corps principal de la Review — résumé du LLM, décompte par sévérité, avertissement Bug 1 si des fichiers ont été tronqués, et liste des commentaires globaux issus du Bug 2.

**Test d'intégration** (`tests/test_review_publisher.py`) : vérifie avec un faux `GitHubClient` (sans réseau) que `create_review` est bien appelé avec la forme exacte attendue par l'API GitHub (`path`, `line`, `side`, `body`), et que le Bug 2 est correctement neutralisé.

## Sprint 5 — Automatisation du workflow & Dashboard (AAR-24 à AAR-29)

⚠️ **Hors périmètre du cahier des charges initial** — ces 6 tickets (labels, checks, auto-approve, dashboard, config par dépôt, métriques) n'apparaissaient pas dans le document d'origine. Traités quand même, avec un point de vigilance :

- **AAR-26 (auto-approve)** touche à la limite du périmètre explicitement **exclu** ("l'agent ne fusionnera pas automatiquement les PR"). Approuver ≠ fusionner, donc ce n'est pas une violation à la lettre, mais l'implémentation reste volontairement **conservatrice** : seuil de lignes strict (30 par défaut, bien en dessous du seuil général US 4.2), zéro problème toléré (même "warning"), et désactivable par dépôt via `.reviewbot.yml`.

| Ticket | Fichier | Rôle |
|---|---|---|
| AAR-24 | `label_manager.py` | Labels (`security-risk`, `needs-changes`, `looks-good`) selon la sévérité |
| AAR-25 | `check_run.py` + `GitHubClient.create_check_run` | Check Run GitHub, exploitable en "required status check" (à activer manuellement dans Settings > Branches du dépôt — l'API ne peut pas configurer la branch protection à la place de l'utilisateur) |
| AAR-26 | `auto_approve.py` + `GitHubClient.approve_pull_request` | Auto-approbation conservatrice des PR mineures (voir avertissement ci-dessus) |
| AAR-27 | `dashboard.py` | Dashboard **en lecture seule** (`/dashboard`, `/api/config`, `/api/metrics`) — pas de persistance d'édition, aucune base de données dans le stack actuel |
| AAR-28 | `config_loader.py` | Surcharge par dépôt via `.reviewbot.yml` (fusion avec les valeurs par défaut, clés inconnues ignorées) |
| AAR-29 | `metrics.py` | Compteurs en mémoire (process unique — à remplacer par une vraie base si l'agent tourne un jour sur plusieurs instances) |

**Nouvelle permission GitHub App requise :** `checks: write` (ajoutée au manifeste et au README) — l'App créée avant ce sprint devra être mise à jour manuellement sur github.com si elle existe déjà.

**Intégration dans `main.py`** : la configuration effective (globale + `.reviewbot.yml`) est chargée une fois par PR, puis utilisée pour le seuil de taille, le plafond de commentaires et le seuil d'auto-approbation — c'est la première fois que le pipeline se comporte différemment selon le dépôt cible.

## Sprint 6 — Déploiement Azure & derniers risques (AAR-33, AAR-34)

### Déploiement sur Azure (US 4.1)

- **`Dockerfile`** : image Python 3.12 slim + Node.js/npm (pour ESLint, AAR-15). ⚠️ Non testé avec un vrai `docker build` dans mon environnement (Docker indisponible côté outils) — à vérifier localement avant un déploiement en confiance.
- **`deploy/azure-setup.sh`** : provisionne toutes les ressources du document de coûts (Container Apps, Container Registry, Key Vault, Log Analytics), construit l'image directement sur Azure (`az acr build`, pas besoin de Docker local).
- **`deploy/link-keyvault-secrets.sh`** : lie les secrets Key Vault à la Container App via identité managée (approche recommandée par Microsoft, pas de secret en clair dans les variables d'environnement).
- **`.github/workflows/deploy.yml`** : pipeline CI/CD (livrable explicite du cahier des charges) — tests à chaque push/PR, déploiement automatique sur `main`.
- **`app/config.py` / `app/github_app.py`** : la clé privée GitHub App peut désormais être fournie directement en variable d'environnement (`GITHUB_PRIVATE_KEY`), pas seulement via un fichier `.pem` local — nécessaire car Azure Container Apps ne permet pas de monter un fichier secret aussi simplement qu'une variable d'environnement.

### AAR-33 [RISQUE] Hallucinations LLM — Faux positifs

Deux mécanismes dans `app/hallucination_guard.py` :
1. **Confiance auto-déclarée** (`ReviewIssue.confidence`, ajoutée au schéma JSON du prompt) — les issues "low" sont écartées par défaut (seuil configurable, `MIN_ISSUE_CONFIDENCE`).
2. **Vérification d'ancrage** (`is_grounded`) : si le message cite un identifiant entre backticks (ex: `` `user_id` ``), il doit apparaître réellement dans la ligne concernée — sinon l'issue est écartée, signe probable d'invention du LLM.

Les issues écartées ne sont jamais publiées, mais leur nombre est mentionné dans le résumé global (AAR-23) pour rester transparent sur ce qui a été filtré.

### AAR-34 [RISQUE] Coûts API LLM — Gros diffs non maîtrisés

`app/cost_guard.py` plafonne le nombre de **chunks** (donc d'appels LLM payants) par revue, indépendamment du nombre de lignes (US 4.2 gère déjà ça) — une PR sous le seuil de lignes mais touchant beaucoup de petits fichiers peut sinon générer un grand nombre d'appels coûteux. Configurable via `MAX_CHUNKS_PER_REVIEW` (8 par défaut). Les fichiers non analysés pour cette raison sont listés dans le résumé, jamais silencieusement ignorés.

### Dashboard interactif (révision AAR-27)

Le dashboard n'est plus un simple tableau HTML statique : l'onglet **"Tester l'agent"** exécute le **vrai pipeline** (linter + patterns + appel LLM réel + filtre anti-hallucination + filtrage + labels + check + auto-approve) sur du code collé par l'utilisateur, sans passer par une vraie Pull Request GitHub — utile pour valider la configuration (clé API, seuils) avant un déploiement.

1. **FastAPI + Python** (retenu suite à la décision du 2026-07) plutôt que Node.js/Express.
2. **Authentification GitHub App par JWT** (`PyJWT` + clé privée RS256), suivant le flux standard à deux étapes (JWT d'App → token d'installation).
3. **Parsing du diff fait "maison"** (regex sur le format unifié) plutôt qu'une librairie tierce, pour garder un contrôle total sur le calcul des numéros de ligne — indispensable pour le futur correctif du Bug 2.
4. **Le garde-fou de taille (US 4.2)** est déjà branché sur `post_issue_comment` : une PR trop volumineuse reçoit immédiatement un commentaire explicatif, sans jamais appeler le LLM (maîtrise des coûts dès ce sprint).
5. **L'appel au LLM n'est volontairement pas encore implémenté** — ce sprint se limite à la chaîne réception → validation → extraction, conformément aux tickets AAR-11 à AAR-14 fournis. Le point d'insertion est clairement marqué par un commentaire `# -> prochaine étape (US 2.2)` dans `main.py`.

## Prochaines étapes (tickets non encore fournis)

- `app/llm/base.py` (interface `LLMProvider`) + `app/llm/openai_provider.py` / `app/llm/anthropic_provider.py`
- `app/review_engine.py` (construction du prompt, orchestration, US 2.2)
- `app/line_validator.py` (Bug 2)
- `app/diff_chunker.py` (Bug 1)
- `app/command_handler.py` (US 3.2, mentions `@ai-reviewer`)
