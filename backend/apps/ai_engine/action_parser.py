"""Parser pour détecter et extraire les propositions d'action depuis les
réponses du LLM.

Format attendu dans la réponse Claude :
    <action>
    {
      "action_type": "create_action_task",
      "summary": "Créer une tâche pour le DAF...",
      "payload": {
        "title": "Finaliser le rapport financier",
        "assignee_email": "daf@kaydan.com",
        "due_date": "2026-06-20",
        "priority": "high"
      }
    }
    </action>

On extrait ce bloc, le valide, et on crée un AIActionRequest(status=PENDING).
La réponse texte conserve le bloc (ou un placeholder) pour que le frontend
puisse afficher une carte d'action séparément.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


ACTION_BLOCK_RE = re.compile(
    r"<action>\s*(\{.*?\})\s*</action>",
    re.DOTALL | re.IGNORECASE,
)

# Liste des action_type acceptés (mirror du choix Django)
VALID_ACTION_TYPES = {
    "create_decision_draft",
    "create_action_task",
    "create_action_plan",
    "assign_task",
    "update_task_status",
    "send_notification",
}


def extract_actions(response_text: str) -> tuple[str, list[dict]]:
    """Extrait les blocs <action>...</action> de la réponse LLM.

    Retourne (texte_nettoyé, liste_d'actions_proposées).
    Le texte nettoyé garde un placeholder lisible à la place du JSON brut.
    """
    if not response_text:
        return response_text, []

    actions: list[dict] = []
    cleaned = response_text

    for match in ACTION_BLOCK_RE.finditer(response_text):
        json_str = match.group(1).strip()
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Action block JSON invalide : %s", json_str[:200])
            continue

        action_type = parsed.get("action_type")
        if action_type not in VALID_ACTION_TYPES:
            logger.warning("Action type non supporté : %s", action_type)
            continue

        # Validation minimale du payload selon le type
        payload = parsed.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        summary = (parsed.get("summary") or "")[:400]

        actions.append({
            "action_type": action_type,
            "summary": summary,
            "payload": payload,
        })

    # Remplace les blocs <action> par un placeholder lisible (sans JSON brut)
    cleaned = ACTION_BLOCK_RE.sub(
        "\n_💡 Action proposée — voir la carte de confirmation ci-dessous._\n",
        cleaned,
    )
    return cleaned, actions


# ─── Prompt à injecter dans le system prompt si actions activées ──────

ACTION_PROMPT_ADDENDUM = """
═══════════════════════════════════════════════════════════════
PROPOSITION D'ACTIONS (TOOL USE simplifié)
═══════════════════════════════════════════════════════════════
Si l'utilisateur te demande explicitement de CRÉER quelque chose dans la
plateforme (une décision, une tâche, un plan d'action), tu peux proposer
l'action en insérant un bloc spécial dans ta réponse :

<action>
{
  "action_type": "create_action_task",
  "summary": "Créer la tâche : Finaliser le rapport Q3 — DAF — vendredi 15 sept",
  "payload": {
    "title": "Finaliser le rapport Q3",
    "description": "...",
    "assignee_email": "daf@kaydan.com",  // ou null si non précisé
    "due_date": "2025-09-15",  // YYYY-MM-DD, ou null
    "priority": "high"  // low/medium/high/critical
  }
}
</action>

Action types disponibles :
- `create_decision_draft` — payload : {title, description, priority, deadline}
- `create_action_task` — payload : {title, description, assignee_email, due_date, priority}
- `create_action_plan` — payload : {title, description, target_end_date}

Règles STRICTES :
1. Ne proposes une action QUE si l'utilisateur l'a explicitement demandée.
2. Le bloc <action> est en plus de ta réponse normale, pas à la place.
3. L'action ne sera PAS exécutée automatiquement — l'utilisateur devra confirmer.
4. Tu peux proposer plusieurs actions dans une même réponse (plusieurs blocs).
5. Si tu ne disposes pas des infos nécessaires (ex: pas d'échéance), mets null
   plutôt que d'inventer.
6. Si la demande est ambiguë, pose une question de clarification AVANT de proposer.

Exemple complet :

Utilisateur : "Crée une tâche pour le DAF avant vendredi : finaliser le budget."

Toi :
> D'accord, je peux proposer la création de cette tâche. Voici les détails que j'ai compris :
>
> <action>
> {
>   "action_type": "create_action_task",
>   "summary": "Créer la tâche : Finaliser le budget — DAF — vendredi",
>   "payload": {
>     "title": "Finaliser le budget",
>     "description": "Tâche demandée via l'Assistant CODIR",
>     "assignee_email": null,
>     "due_date": null,
>     "priority": "medium"
>   }
> }
> </action>
>
> Voulez-vous confirmer ?
"""
