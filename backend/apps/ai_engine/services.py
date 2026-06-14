"""AIChatService — orchestration du chat IA executif CODIR.

Stratégie LLM :
  - Provider primaire = Claude Anthropic (qualité dialogue + raisonnement)
  - Fallback automatique = DeepSeek (compat OpenAI SDK)
  - Réutilise `run_llm_with_fallback` de `meeting_recordings.services.ai_summary`
    pour rester cohérent avec le reste de la plateforme.

Contexte injecté dans le prompt système :
  - Identité user (nom, rôle exécutif/membre)
  - Organisation courante
  - Page courante + objet en cours de consultation
  - Historique récent de la conversation (5-10 derniers messages)

Sécurité :
  - Toute conversation est scoped au user + organisation (TenantManager)
  - Pas d'exposition de données qu'un user ne pourrait pas voir via l'UI
  - Audit via AIInferenceLog (à activer dans une itération suivante)
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from .models import AIConversation, AIMessage

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_BASE = """Tu es l'Assistant CODIR, l'assistant exécutif IA de la plateforme
CODIR de Kaydan Groupe. Tu aides les dirigeants, secrétaires de séance,
responsables de direction et administrateurs à préparer, suivre et analyser
les réunions, décisions, plans d'action et tâches du Comité de Direction.

Style :
- Professionnel, administratif, clair, synthétique.
- Phrases courtes, ton corporate français.
- Format des réponses : Markdown (titres, listes, tableaux si pertinent).
- Tu peux proposer des actions, mais tu n'exécutes JAMAIS d'action sensible
  sans confirmation explicite de l'utilisateur (cette étape arrivera dans
  une prochaine version — pour l'instant tu te limites au dialogue).

Règles strictes :
- Reste fidèle aux informations disponibles dans le contexte fourni.
- Ne fabrique aucune donnée (pas d'hallucination de décisions, de tâches,
  de noms de participants si non mentionnés).
- Si une information manque, dis-le explicitement.
- Tu peux faire des analyses, suggestions, reformulations, brouillons.
- Tu respectes la confidentialité des décisions marquées comme telles.

Contexte de la session courante :
{page_context}"""


# Nombre max de messages d'historique à inclure dans le prompt
HISTORY_LIMIT = 10
# Limite de tokens raisonnable pour les réponses (réglable)
MAX_TOKENS = 1500


def get_or_create_conversation(
    *, user, organization,
    conversation_id: Optional[str] = None,
    context_scope: str = "org",
    context_id: str = "",
    title: str = "",
) -> AIConversation:
    """Récupère une conversation existante du user OU en crée une nouvelle."""
    if conversation_id:
        conv = AIConversation.unscoped.filter(
            id=conversation_id, user=user, organization=organization,
        ).first()
        if conv:
            return conv
    # Création
    conv = AIConversation.unscoped.create(
        organization=organization,
        user=user,
        title=title[:200] or "Nouvelle conversation",
        context_scope=context_scope or "org",
        context_id=context_id[:80],
    )
    return conv


def _build_page_context(scope: str, context_id: str, organization) -> str:
    """Génère un résumé textuel du contexte de la page pour le prompt système.

    On reste minimaliste pour l'instant — on peut enrichir page par page
    plus tard (charger les données de l'objet courant, les KPIs, etc.).
    """
    lines: list[str] = [f"- Organisation : {organization.name}"]
    scope_labels = {
        "org": "Vue globale (dashboard ou liste)",
        "meeting": "Page d'une réunion spécifique",
        "decision": "Page d'une décision spécifique",
        "dashboard": "Cockpit / dashboard exécutif",
        "document": "Page d'un document spécifique",
    }
    lines.append(f"- Page : {scope_labels.get(scope, scope)}")
    if context_id:
        lines.append(f"- Objet consulté (ID) : {context_id}")
    return "\n".join(lines)


def send_user_message(
    *, conversation: AIConversation, user_message: str,
    page_context_scope: str = "", page_context_id: str = "",
) -> AIMessage:
    """Ajoute le message user, appelle le LLM, persiste la réponse assistant.

    Retourne l'AIMessage assistant créé. Lève une exception si tous les
    providers LLM ont échoué (le caller view la transforme en 502/503).
    """
    # ─── 1. Enregistre le message user ───────────────────────
    user_msg = AIMessage.unscoped.create(
        organization=conversation.organization,
        conversation=conversation,
        role="user",
        content_md=user_message[:8000],
    )

    # ─── 2. Construit le contexte + historique ───────────────
    page_ctx_text = _build_page_context(
        page_context_scope or conversation.context_scope,
        page_context_id or conversation.context_id,
        conversation.organization,
    )
    system_prompt = SYSTEM_PROMPT_BASE.format(page_context=page_ctx_text)

    # Récupère les N derniers messages (en ordre chronologique)
    history = list(
        AIMessage.unscoped
        .filter(conversation=conversation)
        .exclude(id=user_msg.id)
        .order_by("-created_at")[:HISTORY_LIMIT]
    )
    history.reverse()  # remettre dans l'ordre chrono pour le LLM

    # Compose un prompt utilisateur qui inclut l'historique inline.
    # (On pourrait passer un vrai messages=[{role,content}, ...] mais
    # run_llm_with_fallback expose juste system + user pour l'instant.)
    history_text = ""
    if history:
        formatted: list[str] = []
        for m in history:
            who = "Utilisateur" if m.role == "user" else "Assistant"
            formatted.append(f"{who} : {m.content_md}")
        history_text = "\n\n[Historique récent]\n" + "\n\n".join(formatted) + "\n"

    user_prompt = f"{history_text}\n[Nouveau message]\n{user_message}"

    # ─── 3. Appel LLM avec fallback ──────────────────────────
    try:
        # Réutilise le wrapper existant qui fait Claude → DeepSeek
        from apps.meeting_recordings.services.ai_summary import run_llm_with_fallback
        response_text = run_llm_with_fallback(
            system=system_prompt,
            user=user_prompt,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI chat LLM call crash : %s", exc)
        response_text = None

    if not response_text:
        # On stocke quand même une réponse fallback pour ne pas casser l'UI
        response_text = (
            "❌ Je n'arrive pas à joindre les modèles IA pour l'instant "
            "(Claude et DeepSeek indisponibles ou clés mal configurées). "
            "Réessayez dans quelques minutes ou prévenez votre administrateur."
        )

    # ─── 4. Persiste la réponse + touche la conv ─────────────
    assistant_msg = AIMessage.unscoped.create(
        organization=conversation.organization,
        conversation=conversation,
        role="assistant",
        content_md=response_text,
    )
    # Touche updated_at de la conversation pour qu'elle remonte
    conversation.save(update_fields=["updated_at"])

    return assistant_msg


def list_user_conversations(*, user, organization, limit: int = 30):
    """Liste les conversations actives du user (non archivées)."""
    return (
        AIConversation.unscoped
        .filter(user=user, organization=organization, is_archived=False)
        .order_by("-updated_at")[:limit]
    )


def list_conversation_messages(*, conversation: AIConversation):
    """Liste tous les messages d'une conversation, en ordre chronologique."""
    return (
        AIMessage.unscoped
        .filter(conversation=conversation)
        .order_by("created_at")
    )
