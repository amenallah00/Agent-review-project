# Conteneurisation de l'agent pour déploiement sur Railway.
#
# Inclut Node.js/npm en plus de Python, car le linter JS/TS (AAR-15, via
# `npx eslint`) en a besoin — sans ça, linter.py dégraderait silencieusement
# (aucun résultat ESLint, mais pas de crash) pour tous les fichiers .js/.ts.

FROM python:3.12-slim

# Dépendances système : libpq pour psycopg2, curl+gnupg pour NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg libpq-dev \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Le port est fourni dynamiquement par Railway via $PORT ;
# 8000 sert de valeur par défaut pour un lancement local (docker run).
ENV PORT=8000
EXPOSE 8000

# La clé privée GitHub App et le fichier .env ne sont JAMAIS copiés dans
# l'image (voir .dockerignore) — ils sont injectés à l'exécution via les
# variables d'environnement Railway.

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
