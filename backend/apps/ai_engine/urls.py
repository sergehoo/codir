"""URLs ai_engine — chat IA MVP.

Routes branchées sous /api/v1/ai-chat/ via config/urls.py.
"""
from django.urls import path

from .views import (
    archive_conversation, conversation_messages,
    list_conversations, send_message,
)


urlpatterns = [
    path("send/",                          send_message,           name="ai-chat-send"),
    path("conversations/",                 list_conversations,     name="ai-chat-conversations"),
    path("conversations/<uuid:pk>/messages/", conversation_messages, name="ai-chat-messages"),
    path("conversations/<uuid:pk>/archive/",  archive_conversation,  name="ai-chat-archive"),
]
