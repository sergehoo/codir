"""URLs ai_engine — chat IA MVP.

Routes branchées sous /api/v1/ai-chat/ via config/urls.py.
"""
from django.urls import path

from .views import (
    archive_conversation, cancel_action, confirm_action,
    conversation_messages, get_action,
    list_conversations, proactive_count, proactive_mark_read,
    semantic_search, send_message,
)


urlpatterns = [
    path("send/",                          send_message,           name="ai-chat-send"),
    path("conversations/",                 list_conversations,     name="ai-chat-conversations"),
    path("conversations/<uuid:pk>/messages/", conversation_messages, name="ai-chat-messages"),
    path("conversations/<uuid:pk>/archive/",  archive_conversation,  name="ai-chat-archive"),
    # ── Actions confirmées ──
    path("actions/<uuid:pk>/",         get_action,     name="ai-chat-action"),
    path("actions/<uuid:pk>/confirm/", confirm_action, name="ai-chat-action-confirm"),
    path("actions/<uuid:pk>/cancel/",  cancel_action,  name="ai-chat-action-cancel"),
    # ── Agent proactif (Lot 2) ──
    path("proactive-count/",      proactive_count,      name="ai-chat-proactive-count"),
    path("proactive-mark-read/",  proactive_mark_read,  name="ai-chat-proactive-mark-read"),
    # ── Recherche sémantique universelle (Lot 3) ──
    path("search/",               semantic_search,      name="ai-chat-search"),
]
