# Agent IA de Revue de Code — Backend

Backend Python/FastAPI de l'agent IA de revue de code (Smartovate Ltd).

## 1. Configurer l'environnement de dev

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Éditez `.env` avec vos propres valeurs (voir section 3).

## 2. Créer la GitHub App (ticket AAR-11)

1. Allez sur `https://github.com/settings/apps/new` (ou celles de votre organisation).
2. Vous pouvez pré-remplir le formulaire en utilisant `github-app-manifest.json`
   (flux "GitHub App Manifest") — remplacez `VOTRE-DOMAINE-OU-NGROK` par
   l'URL ngrok générée à l'étape 4.
3. Permissions à vérifier après création :
   - **Contents** : Read-only
   - **Pull requests** : Read & write
   - **Issues** : Read & write (couvre aussi les labels, AAR-24)
   - **Checks** : Read & write (nécessaire pour le status check AAR-25)
   - **Metadata** : Read-only
4. Dans "Subscribe to events", cochez **Pull request** et **Issue comment**.
5. Générez une clé privée (bouton "Generate a private key" en bas de la page) :
   téléchargez le fichier `.pem` et placez-le dans `secrets/github-app-private-key.pem`
   (dossier déjà présent, **ne jamais commiter ce fichier** — voir `.gitignore`).
6. Notez l'**App ID** affiché en haut de la page → à mettre dans `.env` (`GITHUB_APP_ID`).
7. Générez un secret de webhook aléatoire (ex: `openssl rand -hex 32`) et
   renseignez-le à la fois dans le formulaire GitHub et dans `.env` (`GITHUB_WEBHOOK_SECRET`).
8. Installez l'App sur le dépôt privé de test de Smartovate Ltd.

## 3. Variables d'environnement (`.env`)

| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Identifiant numérique de la GitHub App |
| `GITHUB_PRIVATE_KEY_PATH` | Chemin vers le fichier `.pem` téléchargé à l'étape 2 |
| `GITHUB_WEBHOOK_SECRET` | Secret partagé pour vérifier la signature des webhooks (AAR-13) |
| `LLM_PROVIDER` | `openai` ou `anthropic` (branché dans un ticket ultérieur) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Clé API du fournisseur choisi |
| `MAX_PR_LINES` | Seuil de lignes modifiées au-delà duquel une PR est ignorée (US 4.2) |

## 4. Lancer le serveur en local + exposer via ngrok

```bash
uvicorn app.main:app --reload --port 8000
```

Dans un autre terminal :

```bash
ngrok http 8000
```

Copiez l'URL HTTPS générée par ngrok (ex: `https://abcd1234.ngrok-free.app`),
et mettez à jour l'URL du webhook dans les paramètres de votre GitHub App
(`https://abcd1234.ngrok-free.app/webhook`).

## 5. Vérifier que ça fonctionne

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

Ouvrez ou mettez à jour une Pull Request sur le dépôt où l'App est installée :
les logs du serveur (`uvicorn`) doivent afficher le nombre de fichiers et de
lignes détectés dans le diff.

## 6. Lancer les tests

```bash
pytest
```

## 7. (Optionnel) Linting JavaScript/TypeScript

Le linter Python (`pylint`) est déjà inclus dans `requirements.txt`. Pour que
le linting **JS/TS** (AAR-15) fonctionne aussi, installez Node.js/npm sur la
machine (ou dans l'image Docker de déploiement) — `linter.py` appelle
`npx eslint` à la demande et dégrade silencieusement (aucune erreur) si
Node.js n'est pas disponible.

## 8. Déploiement sur Azure (US 4.1)

### Provisioning des ressources (une seule fois)

Prérequis : [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installé, connecté (`az login`), et un abonnement Azure actif.

```bash
chmod +x deploy/azure-setup.sh deploy/link-keyvault-secrets.sh
./deploy/azure-setup.sh
```

Ce script crée, dans l'ordre : le groupe de ressources, l'**Azure Container Registry**, construit et pousse l'image Docker (directement sur Azure via `az acr build`, **pas besoin de Docker installé en local**), le **Key Vault**, un espace **Log Analytics** (pour Azure Monitor), l'environnement **Container Apps**, puis la **Container App** elle-même.

À la fin, remplacez les valeurs `CHANGEME` dans le Key Vault par vos vraies clés (App ID GitHub, clé privée `.pem`, secret webhook, clé API OpenAI/Anthropic), puis liez-les à la Container App :

```bash
az keyvault secret set --vault-name kv-ai-code-review --name github-private-key --value @secrets/github-app-private-key.pem
az keyvault secret set --vault-name kv-ai-code-review --name github-webhook-secret --value 'votre-secret'
az keyvault secret set --vault-name kv-ai-code-review --name openai-api-key --value 'sk-...'

./deploy/link-keyvault-secrets.sh
```

Récupérez l'URL publique affichée à la fin de `azure-setup.sh`, et mettez à jour l'URL du webhook dans les paramètres de votre GitHub App avec `https://<url>/webhook` (à la place de l'URL ngrok utilisée en développement).

### Déploiements suivants (CI/CD automatique)

Le pipeline `.github/workflows/deploy.yml` lance les tests à chaque push/PR, et déploie automatiquement sur `main` si tout passe. Pour l'activer, configurez dans **Settings → Secrets and variables → Actions** de votre dépôt GitHub :

| Type | Nom | Valeur |
|---|---|---|
| Secret | `AZURE_CREDENTIALS` | JSON généré par `az ad sp create-for-rbac --sdk-auth` (identifiants d'un service principal avec accès au groupe de ressources) |
| Variable | `ACR_NAME` | `acraicodereview` (ou le nom choisi dans `azure-setup.sh`) |
| Variable | `AZURE_RESOURCE_GROUP` | `rg-ai-code-review` |
| Variable | `CONTAINER_APP_NAME` | `ai-code-review-agent` |

⚠️ **Note** : ce Dockerfile n'a pas pu être testé avec un vrai `docker build` dans mon environnement de développement (Docker non installé côté outils). Le script `azure-setup.sh` contourne le problème en construisant l'image directement sur Azure (`az acr build`), mais je vous recommande de faire un premier test local (`docker build -t test .` puis `docker run -p 8000:8000 test`) avant de yous fier au déploiement automatisé, pour détecter d'éventuels problèmes plus tôt.

## Structure du projet

```
app/
  main.py          # Webhook receiver (AAR-12)
  security.py       # Vérification de signature (AAR-13)
  bot_guard.py       # Anti-boucle (Bug 3)
  github_app.py      # Auth GitHub App + client API (AAR-11)
  diff_parser.py      # Parsing et filtrage du diff (AAR-14, US 2.1)
  config.py            # Variables d'environnement
tests/
  test_security.py
  test_diff_parser.py
ARCHITECTURE.md    # Détail de l'architecture (AAR-1)
```

Voir `ARCHITECTURE.md` pour le détail de la conception et les prochaines étapes.
