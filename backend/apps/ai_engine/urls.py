"""URLs ai_engine — chat IA MVP.

Routes branchées sous /api/v1/ai-chat/ via config/urls.py.
"""
from django.urls import path

from .views import (
    archive_conversation, cancel_action, confirm_action,
    conversation_messages, get_action,
    list_conversations, send_message,
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
]
