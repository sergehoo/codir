"""Serializers DRF — action_plans."""
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import ActionComment, ActionEvidence, ActionPlan, ActionTask


def _resolve_subsidiary(action_plan):
    """Remonte la chaîne action_plan → decision → direction → subsidiary."""
    try:
        decision = action_plan.decision
        direction = getattr(decision, "direction", None)
        if direction and direction.subsidiary:
            return direction.subsidiary
    except Exception:  # noqa: BLE001
        return None
    return None


class ActionCommentSerializer(serializers.ModelSerializer):
    author_detail = UserMiniSerializer(source="author", read_only=True)

    class Meta:
        model = ActionComment
        fields = ["id", "task", "action_plan", "author", "author_detail", "body_md", "created_at"]
        read_only_fields = ("author", "created_at")


class ActionEvidenceSerializer(serializers.ModelSerializer):
    submitted_by_detail = UserMiniSerializer(source="submitted_by", read_only=True)

    class Meta:
        model = ActionEvidence
        fields = [
            "id", "task", "document", "url", "description",
            "submitted_by", "submitted_by_detail", "created_at",
        ]
        read_only_fields = ("submitted_by", "created_at")


class ActionTaskListSerializer(serializers.ModelSerializer):
    assignee_detail = UserMiniSerializer(source="assignee", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    subsidiary_id = serializers.SerializerMethodField()
    subsidiary_name = serializers.SerializerMethodField()
    action_plan_title = serializers.CharField(source="action_plan.title", read_only=True)

    class Meta:
        model = ActionTask
        fields = [
            "id", "action_plan", "action_plan_title",
            "parent", "title", "priority", "status",
            "assignee", "assignee_detail",
            "due_date", "progress_percent",
            "started_at", "completed_at",
            "is_overdue",
            "subsidiary_id", "subsidiary_name",
            "created_at", "updated_at",
        ]

    def get_subsidiary_id(self, obj):
        sub = _resolve_subsidiary(obj.action_plan)
        return str(sub.id) if sub else None

    def get_subsidiary_name(self, obj):
        sub = _resolve_subsidiary(obj.action_plan)
        return sub.name if sub else None


class ActionTaskDetailSerializer(ActionTaskListSerializer):
    comments = ActionCommentSerializer(many=True, read_only=True)
    evidence = ActionEvidenceSerializer(many=True, read_only=True)
    subtasks = ActionTaskListSerializer(many=True, read_only=True)

    class Meta(ActionTaskListSerializer.Meta):
        fields = ActionTaskListSerializer.Meta.fields + [
            "description_md", "effort_estimate_hours", "effort_actual_hours",
            "comments", "evidence", "subtasks",
        ]


class ActionTaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionTask
        fields = [
            "parent", "title", "description_md", "priority",
            "assignee", "due_date", "effort_estimate_hours",
        ]


class ActionPlanListSerializer(serializers.ModelSerializer):
    owner_detail = UserMiniSerializer(source="owner", read_only=True)
    tasks_count = serializers.SerializerMethodField()
    subsidiary_id = serializers.SerializerMethodField()
    subsidiary_name = serializers.SerializerMethodField()
    direction_id = serializers.SerializerMethodField()
    direction_name = serializers.SerializerMethodField()
    decision_ref = serializers.CharField(source="decision.ref", read_only=True)
    can_add_tasks = serializers.SerializerMethodField()
    can_modify = serializers.SerializerMethodField()

    class Meta:
        model = ActionPlan
        fields = [
            "id", "decision", "decision_ref", "title", "status", "progress_percent",
            "owner", "owner_detail",
            "start_date", "target_end_date", "actual_end_date",
            "tasks_count",
            "subsidiary_id", "subsidiary_name",
            "direction_id", "direction_name",
            "can_add_tasks", "can_modify",
            "created_at", "updated_at",
        ]

    def get_tasks_count(self, obj):
        return getattr(obj, "_tasks_count", obj.tasks.count())

    def get_subsidiary_id(self, obj):
        sub = _resolve_subsidiary(obj)
        return str(sub.id) if sub else None

    def get_subsidiary_name(self, obj):
        sub = _resolve_subsidiary(obj)
        return sub.name if sub else None

    def get_direction_id(self, obj):
        decision = getattr(obj, "decision", None)
        direction = getattr(decision, "direction", None) if decision else None
        return str(direction.id) if direction else None

    def get_direction_name(self, obj):
        decision = getattr(obj, "decision", None)
        direction = getattr(decision, "direction", None) if decision else None
        return direction.name if direction else None

    def get_can_add_tasks(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        user = getattr(request, "user", None) if request else None
        if user is None or not user.is_authenticated:
            return False
        from .services import user_can_add_tasks_to_plan
        return user_can_add_tasks_to_plan(user, obj)

    def get_can_modify(self, obj):
        """True si le user courant peut modifier/supprimer ce plan."""
        request = self.context.get("request") if hasattr(self, "context") else None
        if request is None:
            return False
        from apps.common.permissions import CanModifyActionPlan
        perm = CanModifyActionPlan()
        return perm.has_object_permission(request, None, obj)


class ActionPlanDetailSerializer(ActionPlanListSerializer):
    tasks = ActionTaskDetailSerializer(many=True, read_only=True)
    comments = ActionCommentSerializer(many=True, read_only=True)

    class Meta(ActionPlanListSerializer.Meta):
        fields = ActionPlanListSerializer.Meta.fields + [
            "description_md", "tasks", "comments",
        ]


class UpdateProgressSerializer(serializers.Serializer):
    progress_percent = serializers.IntegerField(min_value=0, max_value=100)
    status = serializers.CharField(required=False, allow_blank=True)
