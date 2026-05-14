"""Serializers smart-notes."""
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import (
    MeetingDetectedAction, MeetingDetectedDecision,
    MeetingMention, MeetingNote,
)


class MeetingNoteFullSerializer(serializers.ModelSerializer):
    author_detail = UserMiniSerializer(source="author", read_only=True)

    class Meta:
        model = MeetingNote
        fields = [
            "id", "meeting", "author", "author_detail",
            "content_md", "content_json",
            "version", "is_current", "is_private",
            "last_autosaved_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "version", "is_current", "last_autosaved_at",
                            "created_at", "updated_at", "author", "author_detail"]


class MeetingDetectedActionSerializer(serializers.ModelSerializer):
    assignee_detail = UserMiniSerializer(source="assignee", read_only=True)

    class Meta:
        model = MeetingDetectedAction
        fields = [
            "id", "title", "raw_line",
            "assignee", "assignee_detail", "assignee_mention",
            "order", "status",
            "action_task", "published_at",
            "detected_decision",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class MeetingDetectedDecisionSerializer(serializers.ModelSerializer):
    actions = MeetingDetectedActionSerializer(many=True, read_only=True)

    class Meta:
        model = MeetingDetectedDecision
        fields = [
            "id", "title", "raw_line", "order", "status",
            "decision", "published_at",
            "actions",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class MeetingMentionSerializer(serializers.ModelSerializer):
    user_detail = UserMiniSerializer(source="user", read_only=True)

    class Meta:
        model = MeetingMention
        fields = ["id", "raw_text", "user", "user_detail", "occurrences", "created_at"]
        read_only_fields = fields
