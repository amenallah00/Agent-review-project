"""
Bug 3 (anticipé dans le cahier des charges) : boucle infinie si l'agent
réagit à ses propres commentaires ou à ceux d'un autre bot.
"""


def is_bot_sender(payload: dict) -> bool:
    """
    Retourne True si l'événement a été déclenché par un compte bot
    (notre agent lui-même, ou tout autre bot GitHub), auquel cas il doit
    être ignoré silencieusement par le webhook receiver.
    """
    sender = payload.get("sender", {})

    if sender.get("type") == "Bot":
        return True

    login = sender.get("login", "")
    if login.endswith("[bot]"):
        return True

    return False
