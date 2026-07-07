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
    # Cockpit prédictif — Lot 1 : santé calculée à la volée.
    health_score = serializers.SerializerMethodField()
    health_label = serializers.SerializerMethodField()
    health_reasons = serializers.SerializerMethodField()
    # Rattachement organisationnel (Fil-Dir) : id + nom prêts à afficher
    subsidiary_name = serializers.CharField(source="subsidiary.name", read_only=True, allow_null=True)
    direction_name = serializers.CharField(source="direction.name", read_only=True, allow_null=True)

    class Meta:
        model = Decision
        fields = [
            "id", "ref", "title", "status", "priority", "impact",
            "responsible", "responsible_detail",
            "category", "category_detail",
            "subsidiary", "subsidiary_name",
            "direction", "direction_name",
            "deadline", "is_confidential",
            "meeting", "agenda_item",
            "health_score", "health_label", "health_reasons",
            "created_at", "updated_at",
        ]

    def _health(self, obj):
        cached = getattr(obj, "_cached_health", None)
        if cached is None:
            from apps.common.health_score import compute_decision_health
            cached = compute_decision_health(obj)
            obj._cached_health = cached
        return cached

    def get_health_score(self, obj):
        return self._health(obj).score

    def get_health_label(self, obj):
        return self._health(obj).label

    def get_health_reasons(self, obj):
        return self._health(obj).reasons


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
        # related_name est devenu "action_plans" (pluriel) après la migration
        # OneToOneField → ForeignKey. On vérifie qu'au moins un plan est lié.
        return obj.action_plans.exists()


class DecisionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = [
            "title", "description_md",
            "meeting", "agenda_item",
            # Rattachement organisationnel — filiale et/ou direction
            "subsidiary", "direction",
            "category",
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
