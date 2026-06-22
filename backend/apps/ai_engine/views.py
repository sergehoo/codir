"""DRF views ai_engine — chat IA MVP.

Endpoints :
  POST /api/v1/ai-chat/send/                       → envoie un message + récupère réponse
  GET  /api/v1/ai-chat/conversations/              → liste les conversations du user
  GET  /api/v1/ai-chat/conversations/{id}/messages/ → messages d'une conv
  POST /api/v1/ai-chat/conversations/{id}/archive/ → archive une conv
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes as drf_permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsOrganizationMember

from django.utils import timezone

from .action_executors import execute_action
from .models import AIActionRequest, AIConversation
from .serializers import (
    AIActionRequestSerializer, AIConversationSerializer,
    AIMessageSerializer, SendMessageSerializer,
)
from .services import (
    get_or_create_conversation, list_conversation_messages,
    list_user_conversations, send_user_message,
)

logger = logging.getLogger(__name__)


def _get_org(request):
    """Helper : récupère l'org depuis la requête (set par TenantMiddleware)."""
    return getattr(request, "organization", None)


@api_view(["POST"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def send_message(request):
    """POST /ai-chat/send/

    Body : { message, conversation_id?, context_scope?, context_id?, new_conversation_title? }
    Réponse : { conversation: {...}, user_message: {...}, assistant_message: {...} }
    """
    ser = SendMessageSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    org = _get_org(request)
    if org is None:
        return Response(
            {"detail": "Aucune organisation active. Reconnectez-vous."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Résout / crée la conversation
    try:
        conv = get_or_create_conversation(
            user=request.user, organization=org,
            conversation_id=str(data["conversation_id"]) if data.get("conversation_id") else None,
            context_scope=data.get("context_scope") or "org",
            context_id=data.get("context_id") or "",
            title=data.get("new_conversation_title") or "",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI chat get_or_create_conversation KO")
        return Response(
            {"detail": f"Impossible d'ouvrir la conversation : {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Envoie le message + récupère la réponse LLM
    try:
        assistant_msg = send_user_message(
            conversation=conv,
            user_message=data["message"],
            page_context_scope=data.get("context_scope") or "",
            page_context_id=data.get("context_id") or "",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI chat send_user_message crash")
        return Response(
            {"detail": f"Erreur LLM : {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # On renvoie les 2 derniers messages (user + assistant) + la conv mise à jour
    msgs = list(list_conversation_messages(conversation=conv).order_by("-created_at")[:2])
    msgs.reverse()
    return Response(
        {
            "conversation": AIConversationSerializer(conv).data,
            "messages": AIMessageSerializer(msgs, many=True).data,
            "assistant_message": AIMessageSerializer(assistant_msg).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def list_conversations(request):
    """GET /ai-chat/conversations/ — liste les conversations actives du user."""
    org = _get_org(request)
    if org is None:
        return Response({"results": []})
    convs = list_user_conversations(user=request.user, organization=org)
    return Response({
        "results": AIConversationSerializer(convs, many=True).data,
    })


@api_view(["GET"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def conversation_messages(request, pk):
    """GET /ai-chat/conversations/{id}/messages/"""
    org = _get_org(request)
    if org is None:
        return Response({"results": []})
    conv = get_object_or_404(
        AIConversation.unscoped,
        id=pk, user=request.user, organization=org,
    )
    msgs = list_conversation_messages(conversation=conv)
    return Response({
        "conversation": AIConversationSerializer(conv).data,
        "messages": AIMessageSerializer(msgs, many=True).data,
    })


@api_view(["GET"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def get_action(request, pk):
    """GET /ai-chat/actions/{id}/ — détail d'une action proposée."""
    org = _get_org(request)
    action = get_object_or_404(
        AIActionRequest.unscoped,
        id=pk, requested_by=request.user, organization=org,
    )
    return Response(AIActionRequestSerializer(action).data)


@api_view(["POST"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def confirm_action(request, pk):
    """POST /ai-chat/actions/{id}/confirm/

    Confirme une AIActionRequest et exécute l'action correspondante
    (création de décision, tâche, plan, etc.). Retourne l'objet créé.
    """
    org = _get_org(request)
    action = get_object_or_404(
        AIActionRequest.unscoped,
        id=pk, requested_by=request.user, organization=org,
    )

    if action.status not in ("pending",):
        return Response(
            {
                "detail": f"Action déjà au statut '{action.status}' — "
                          "confirmation impossible.",
                "code": "invalid_state",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Marque confirmée puis exécute
    action.status = "confirmed"
    action.confirmed_at = timezone.now()
    action.save(update_fields=["status", "confirmed_at", "updated_at"])

    action = execute_action(action)
    return Response(AIActionRequestSerializer(action).data)


@api_view(["POST"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def cancel_action(request, pk):
    """POST /ai-chat/actions/{id}/cancel/"""
    org = _get_org(request)
    action = get_object_or_404(
        AIActionRequest.unscoped,
        id=pk, requested_by=request.user, organization=org,
    )

    if action.status not in ("pending",):
        return Response(
            {"detail": "Cette action ne peut plus être annulée.",
             "code": "invalid_state"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    action.status = "cancelled"
    action.save(update_fields=["status", "updated_at"])
    return Response(AIActionRequestSerializer(action).data)


@api_view(["GET"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def proactive_count(request):
    """GET /ai-chat/proactive-count/

    Compte les alertes proactives non lues du user dans l'org courante.
    Utilisé par le bouton chat IA pour afficher un badge.
    """
    from .models import ProactiveAlert
    org = _get_org(request)
    if org is None:
        return Response({"count": 0})
    count = (
        ProactiveAlert.unscoped
        .filter(organization=org, user=request.user, status="emitted")
        .count()
    )
    return Response({"count": count})


@api_view(["POST"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def proactive_mark_read(request):
    """POST /ai-chat/proactive-mark-read/

    Marque toutes les alertes proactives `emitted` du user comme `read`.
    Appelé par le frontend quand le user ouvre la conversation proactive.
    """
    from .models import ProactiveAlert
    org = _get_org(request)
    if org is None:
        return Response({"updated": 0})
    updated = (
        ProactiveAlert.unscoped
        .filter(organization=org, user=request.user, status="emitted")
        .update(status="read", read_at=timezone.now())
    )
    return Response({"updated": updated})


@api_view(["GET"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def semantic_search(request):
    """GET /ai-chat/search/?q=...&kinds=decision,plan&limit=20

    Recherche sémantique cross-modules dans l'org courante.
    Filtre obligatoire par tenant (sécurité multi-org).
    """
    from .indexing import search
    org = _get_org(request)
    if org is None:
        return Response({"results": [], "count": 0, "query": ""})

    query = (request.query_params.get("q") or "").strip()
    if not query:
        return Response({"results": [], "count": 0, "query": ""})

    try:
        limit = max(1, min(int(request.query_params.get("limit", 20)), 50))
    except (ValueError, TypeError):
        limit = 20

    kinds_raw = request.query_params.get("kinds", "")
    kinds = [k.strip() for k in kinds_raw.split(",") if k.strip()] or None

    try:
        results = search(
            organization=org, query=query, limit=limit, kinds=kinds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("semantic_search KO")
        return Response(
            {"detail": f"Erreur recherche : {exc}", "results": [], "count": 0},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response({
        "query": query,
        "results": results,
        "count": len(results),
    })


@api_view(["POST"])
@drf_permission_classes([IsAuthenticated, IsOrganizationMember])
def archive_conversation(request, pk):
    """POST /ai-chat/conversations/{id}/archive/"""
    org = _get_org(request)
    if org is None:
        return Response({"detail": "Pas d'org"}, status=400)
    conv = get_object_or_404(
        AIConversation.unscoped,
        id=pk, user=request.user, organization=org,
    )
    conv.is_archived = True
    conv.save(update_fields=["is_archived", "updated_at"])
    return Response(AIConversationSerializer(conv).data)
