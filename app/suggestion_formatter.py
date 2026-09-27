"""
AAR-22 : Génération de suggestions de code applicables (bloc Markdown
```suggestion``` de GitHub), pour que le développeur puisse accepter la
correction proposée d'un clic depuis l'onglet "Files changed" (US 3.1 :
"Les commentaires incluent des suggestions de code applicables").
"""

from .llm.base import ReviewIssue

SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟡", "info": "🔵"}


def format_comment_body(issue: ReviewIssue) -> str:
    """
    Construit le corps Markdown d'un commentaire inline : le message
    (préfixé d'un emoji de sévérité), suivi d'un bloc ```suggestion```
    si le LLM a proposé un remplacement de code directement applicable.
    """
    emoji = SEVERITY_EMOJI.get(issue.severity, "")
    body = f"{emoji} **[{issue.severity.upper()}]** {issue.message}"

    if issue.suggestion:
        body += f"\n\n```suggestion\n{issue.suggestion}\n```"

    return body
