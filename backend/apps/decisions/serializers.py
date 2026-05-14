"""Serializers DRF — decisions."""
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import (
    Decision, DecisionCategory, DecisionComment, DecisionHistory,
)


class DecisionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionCategory
        fields = ["id", "name", "color", "description"]


class DecisionHistorySerializer(serializers.ModelSerializer):
    actor_detail = UserMiniSerializer(source="actor", read_only=True)

    class Meta:
        model = DecisionHistory
        fields = ["id", "decision", "actor", "actor_detail", "event", "description", "metadata", "created_at"]
        read_only_fields = fields


class DecisionCommentSerializer(serializers.ModelSerializer):
    author_detail = UserMiniSerializer(source="author", read_only=True)

    class Meta:
        model = DecisionComment
        fields = ["id", "decision", "author", "author_detail", "body_md", "created_at"]
        read_only_fields = ("author", "decision", "created_at")


class DecisionListSerializer(serializers.ModelSerializer):
    responsible_detail = UserMiniSerializer(source="responsible", read_only=True)
    category_detail = DecisionCategorySerializer(source="category", read_only=True)

    class Meta:
        model = Decision
        fields = [
            "id", "ref", "title", "status", "priority", "impact",
            "responsible", "responsible_detail",
            "category", "category_detail",
            "direction", "deadline", "is_confidential",
            "meeting", "agenda_item",
            "created_at", "updated_at",
        ]


class DecisionDetailSerializer(DecisionListSerializer):
    approved_by_detail = UserMiniSerializer(source="approved_by", read_only=True)
    history = DecisionHistorySerializer(many=True, read_only=True)
    comments = DecisionCommentSerializer(many=True, read_only=True)
    has_action_plan = serializers.SerializerMethodField()

    class Meta(DecisionListSerializer.Meta):
        fields = DecisionListSerializer.Meta.fields + [
            "description_md", "approved_at", "approved_by", "approved_by_detail",
            "completed_at", "history", "comments", "has_action_plan",
        ]

    def get_has_action_plan(self, obj):
        return hasattr(obj, "action_plan")


class DecisionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = [
            "title", "description_md",
            "meeting", "agenda_item", "direction", "category",
            "priority", "impact", "responsible", "deadline",
            "is_confidential",
        ]


class ApproveDecisionSerializer(serializers.Serializer):
    pass


class ConvertToActionPlanSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=300)
    description_md = serializers.CharField(required=False, allow_blank=True)
    target_end_date = serializers.DateField(required=False, allow_null=True)
    tasks = serializers.ListField(child=serializers.DictField(), required=False)
