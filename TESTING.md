# Guide de test — Comment vérifier que l'agent fonctionne parfaitement

5 niveaux, du plus rapide (quelques secondes, aucune clé API réelle
nécessaire) au plus réaliste (vraie PR GitHub, puis Azure). Faites-les
dans l'ordre : chaque niveau valide une couche différente, inutile de
sauter au niveau 3 si le niveau 1 échoue déjà.

---

## Niveau 1 — Tests automatisés (30 secondes, sans aucune clé API)

```bash
pytest -q
```

**Résultat attendu :** `100 passed`. Si un test échoue, c'est un vrai bug dans le code — ne passez pas aux niveaux suivants tant que ce n'est pas corrigé, les autres niveaux ne feront que masquer le problème avec du bruit réseau.

---

## Niveau 2 — Dashboard interactif (2 minutes, avec une vraie clé API)

C'est le moyen le plus rapide de tester le **vrai** comportement de l'agent (linter + patterns + LLM + labels + check + auto-approve) sans avoir besoin de GitHub du tout.

```bash
cp .env.example .env
# éditez .env : renseignez au minimum OPENAI_API_KEY (ou ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic)
uvicorn app.main:app --reload --port 8000
```

Ouvrez **http://localhost:8000/dashboard**, onglet "Tester l'agent". Testez ces 4 scénarios pour couvrir les cas essentiels :

| Scénario | Code à coller | Résultat attendu |
|---|---|---|
| **Code propre** | `def add(a, b):\n    return a + b` | 0 issue, label `looks-good`, check `success`, auto-approve = Oui |
| **Injection SQL** | `query = "SELECT * FROM users WHERE id=" + user_id` | Issue `critical`, label `security-risk`, check `failure` |
| **Secret en dur** | `api_key = "sk-abcdef1234567890"` | Détecté par `pattern_matches` (AAR-16) ET dans le prompt réel envoyé au LLM, la valeur doit être masquée (`[REDACTED]`) — vérifiable en ajoutant un log temporaire si besoin |
| **Style JS discutable** | fichier `test.js` avec `if (x == null)` | Détecté par ESLint (si Node.js installé) et/ou le pattern `loose_equality_js` |

Si le champ `error` apparaît dans les résultats → votre clé API est invalide ou absente, corrigez `.env` avant de continuer.

---

## Niveau 3 — Test end-to-end avec une vraie Pull Request (15-20 minutes)

C'est le seul niveau qui valide **tout** le pipeline, y compris les parties qui ne passent pas par le dashboard : réception du webhook, signature, publication réelle sur GitHub, labels, check run.

### Préparation
1. Suivez `README.md` §2 pour créer la GitHub App (si pas déjà fait) et l'installer sur un **dépôt de test** dédié (ne testez pas sur un dépôt de production).
2. `uvicorn app.main:app --reload --port 8000` + `ngrok http 8000` dans un second terminal.
3. Mettez à jour l'URL du webhook de la GitHub App avec l'URL ngrok + `/webhook`.

### Scénarios à tester, un par un

| # | Ce que vous testez | Comment | Ce qu'il faut observer |
|---|---|---|---|
| 1 | **Flux nominal** | Ouvrez une PR avec un fichier contenant un bug volontaire (ex: injection SQL) | Commentaire inline posté sur la bonne ligne, résumé en haut de la revue, label `security-risk`, check "AI Code Review" visible dans l'onglet Checks |
| 2 | **US 4.2 (PR trop grosse)** | Modifiez > 500 lignes d'un coup | Un seul commentaire d'avertissement posté, **aucun appel LLM** (vérifiable dans les logs `uvicorn`) |
| 3 | **Bug 3 (anti-boucle)** | Laissez l'agent poster un commentaire, puis regardez s'il réagit à son propre commentaire | Aucune réaction dans les logs (`"Événement ignoré (émetteur = bot)"`) |
| 4 | **AAR-26 (auto-approve)** | PR de moins de 30 lignes, sans aucun problème | La PR doit apparaître comme "Approved" dans l'onglet Reviews de GitHub |
| 5 | **AAR-28 (config par repo)** | Ajoutez un `.reviewbot.yml` à la racine avec `max_pr_lines: 50`, puis testez avec une PR de 60 lignes | La PR doit être ignorée à 60 lignes alors que le seuil global (`.env`) est 500 |
| 6 | **Bug 1 (chunking)** | Un seul fichier avec un très gros refactoring (>2000 lignes generées) | Logs mentionnant `"fichier(s) tronqué(s) (Bug 1)"`, et le résumé de la PR sur GitHub doit afficher l'avertissement correspondant |
| 7 | **AAR-34 (plafond de coût)** | PR touchant plus de 8 fichiers différents, chacun assez gros pour former son propre chunk | Logs `"AAR-34 : N chunk(s) non analysé(s)"`, résumé GitHub mentionnant les fichiers non analysés |
| 8 | **AAR-35 (fichiers sensibles)** | PR modifiant un fichier `.env` ou `secrets.yaml` | Ce fichier ne doit apparaître nulle part dans l'analyse (ni logs, ni résumé) — silencieusement exclu dès AAR-14 |

Après chaque test, vérifiez `http://localhost:8000/api/metrics` (ou l'onglet Métriques du dashboard) : les compteurs doivent augmenter de façon cohérente.

---

## Niveau 4 — Ce qui n'est PAS encore couvert (ne testez pas, ça n'existe pas encore)

- **US 3.2** : mentionner `@ai-reviewer` dans un commentaire ne déclenche encore rien (juste un log) — pas un bug, simplement pas implémenté.
- **AAR-25 (required check)** : le Check Run est bien publié, mais il faut l'activer manuellement comme "required" dans Settings > Branches du dépôt pour qu'il bloque réellement un merge.

---

## Niveau 5 — Une fois déployé sur Azure

Refaites le Niveau 3 en pointant le webhook GitHub vers l'URL Azure (`https://<votre-app>.azurecontainerapps.io/webhook`) au lieu de ngrok, puis vérifiez en plus :

```bash
curl https://<votre-app>.azurecontainerapps.io/health
```

Et consultez les logs réels dans le portail Azure (Container App → Log stream, ou via Log Analytics) plutôt que votre terminal local — c'est le seul moyen de confirmer que les secrets Key Vault sont bien résolus en production (une clé API mal configurée à ce niveau se manifeste par des erreurs `401`/`403` dans les logs, sans faire planter le conteneur grâce à la gestion d'erreurs déjà en place).

---

## Checklist rapide avant de dire "ça marche"

- [ ] `pytest -q` → 100 passed
- [ ] Dashboard : les 4 scénarios du Niveau 2 donnent le résultat attendu
- [ ] Une vraie PR de test reçoit un commentaire cohérent avec son contenu
- [ ] Une PR trop grosse est bien ignorée sans appeler le LLM
- [ ] Une PR propre et petite est auto-approuvée
- [ ] `/api/metrics` reflète bien l'activité observée
