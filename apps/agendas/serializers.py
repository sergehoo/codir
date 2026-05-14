"""Serializers DRF — agendas."""
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import Agenda, AgendaItem, AgendaItemComment


class AgendaItemCommentSerializer(serializers.ModelSerializer):
    author_detail = UserMiniSerializer(source="author", read_only=True)

    class Meta:
        model = AgendaItemComment
        fields = ["id", "item", "author", "author_detail", "body_md", "created_at"]
        read_only_fields = ("author", "created_at", "item")


class AgendaItemSerializer(serializers.ModelSerializer):
    responsible_detail = UserMiniSerializer(source="responsible", read_only=True)
    comments = AgendaItemCommentSerializer(many=True, read_only=True)

    class Meta:
        model = AgendaItem
        fields = [
            "id", "agenda", "order", "title", "description_md",
            "priority", "estimated_duration_minutes", "actual_duration_minutes",
            "responsible", "responsible_detail",
            "status", "started_at", "completed_at",
            "discussion_notes_md", "comments",
            "created_at", "updated_at",
        ]
        read_only_fields = ("agenda", "order", "started_at", "completed_at")


class AgendaSerializer(serializers.ModelSerializer):
    items = AgendaItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    total_estimated_minutes = serializers.IntegerField(read_only=True)
    validated_by_detail = UserMiniSerializer(source="validated_by", read_only=True)

    class Meta:
        model = Agenda
        fields = [
            "id", "meeting", "is_validated", "validated_at",
            "validated_by", "validated_by_detail",
            "notes_md", "items",
            "items_count", "total_estimated_minutes",
            "created_at", "updated_at",
        ]
        read_only_fields = ("is_validated", "validated_at", "validated_by", "meeting")


class ReorderItemsSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(child=serializers.UUIDField())


class DiscussItemSerializer(serializers.Serializer):
    notes_md = serializers.CharField(required=False, allow_blank=True)


class PostponeItemSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=400)
