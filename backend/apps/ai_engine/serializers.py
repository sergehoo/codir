"""Serializers ai_engine — chat IA MVP."""
from rest_framework import serializers

from .models import AIActionRequest, AIConversation, AIMessage


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = [
            "id", "role", "content_md", "tokens",
            "created_at", "feedback", "citations_json",
        ]
        read_only_fields = fields


class AIConversationSerializer(serializers.ModelSerializer):
    last_message_at = serializers.DateTimeField(source="updated_at", read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AIConversation
        fields = [
            "id", "title", "context_scope", "context_id",
            "is_archived", "created_at", "updated_at",
            "last_message_at", "message_count",
        ]
        read_only_fields = ("id", "created_at", "updated_at", "message_count")

    def get_message_count(self, obj):
        return obj.messages.count()


class AIActionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIActionRequest
        fields = [
            "id", "action_type", "summary", "payload", "status",
            "confirmed_at", "executed_at", "error_message",
            "result_object_type", "result_object_id",
            "created_at",
        ]
        read_only_fields = (
            "id", "confirmed_at", "executed_at", "error_message",
            "result_object_type", "result_object_id", "created_at",
        )


class SendMessageSerializer(serializers.Serializer):
    """POST /api/v1/ai-chat/send/"""
    message = serializers.CharField(max_length=8000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    # Contexte page (optionnel)
    context_scope = serializers.ChoiceField(
        choices=AIConversation.SCOPE, required=False, allow_blank=True,
    )
    context_id = serializers.CharField(max_length=80, required=False, allow_blank=True)
    # Pour créer une nouvelle conv : titre suggéré
    new_conversation_title = serializers.CharField(
        max_length=200, required=False, allow_blank=True,
    )
