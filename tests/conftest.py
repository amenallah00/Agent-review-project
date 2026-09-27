"""
Fournit des variables d'environnement factices pour que la suite de tests
puisse s'exécuter sans `.env` réel (aucune vraie clé API/GitHub n'est
nécessaire pour les tests, qui n'appellent jamais les API externes).

`setdefault` ne touche jamais une variable déjà définie : si un vrai `.env`
est chargé (ex: exécution locale avec vos propres clés), ces valeurs de
test restent sans effet.
"""

import os

os.environ.setdefault("GITHUB_APP_ID", "123456")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
