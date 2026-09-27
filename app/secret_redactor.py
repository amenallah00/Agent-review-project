"""
AAR-35 [RISQUE] Sécurité — Exposition du code source au LLM.

Envoyer le code d'une PR à une API tierce (OpenAI/Anthropic) est inhérent
à la fonctionnalité (US 2.2), mais ça ne doit jamais inclure de secrets
réels ni le contenu de fichiers manifestement sensibles. Deux mécanismes :

1. `is_sensitive_file` : exclusion complète de certains fichiers avant même
   l'extraction du diff (clés privées, .env, identifiants...).
2. `redact_secrets` : masque la VALEUR d'un secret apparent dans le texte
   envoyé au LLM, en gardant le nom de la variable visible pour le contexte.
"""

import re

# Fichiers jamais envoyés au LLM, quel que soit leur contenu.
SENSITIVE_FILENAME_PATTERNS = [
    r"\.env(\..+)?$",
    r"\.pem$",
    r"\.key$",
    r"^id_rsa$",
    r"^id_ed25519$",
    r"credentials\.json$",
    r"secrets?\.ya?ml$",
    r"\.pfx$",
    r"\.p12$",
    r"\.pkcs12$",
]

# Reprend le même motif que pattern_detector.hardcoded_secret (AAR-16),
# mais ici pour MASQUER la valeur plutôt que juste la signaler.
_SECRET_VALUE_RE = re.compile(
    r"((?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*[\"'])([^\"']{8,})([\"'])",
    re.IGNORECASE,
)


def is_sensitive_file(filename: str) -> bool:
    """Retourne True si ce fichier ne doit jamais être envoyé au LLM, en aucune circonstance."""
    return any(re.search(pattern, filename, re.IGNORECASE) for pattern in SENSITIVE_FILENAME_PATTERNS)


def redact_secrets(text: str) -> str:
    """
    Remplace la valeur d'un secret apparent par [REDACTED] avant que le
    texte n'entre dans le prompt envoyé au LLM. Le nom de la variable
    (ex: `api_key =`) reste visible, pas sa valeur.
    """
    return _SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}[REDACTED]{m.group(3)}", text)
