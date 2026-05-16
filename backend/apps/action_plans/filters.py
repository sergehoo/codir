from django_filters import rest_framework as filters

from .models import ActionPlan, ActionTask


class ActionPlanFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status")
    owner = filters.UUIDFilter(field_name="owner_id")
    decision = filters.UUIDFilter(field_name="decision_id")

    class Meta:
        model = ActionPlan
        fields = ["status", "owner", "decision"]


class ActionTaskFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status")
    assignee = filters.UUIDFilter(field_name="assignee_id")
    action_plan = filters.UUIDFilter(field_name="action_plan_id")
    priority = filters.CharFilter(field_name="priority")
    due_before = filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    overdue = filters.BooleanFilter(method="filter_overdue")
    # ─── Live CODIR Mode ───
    meeting = filters.UUIDFilter(field_name="action_plan__decision__meeting_id")
    decision = filters.UUIDFilter(field_name="action_plan__decision_id")
    direction = filters.UUIDFilter(field_name="action_plan__decision__direction_id")

    def filter_overdue(self, qs, name, value):
        from django.utils import timezone
        if value:
            return qs.filter(due_date__lt=timezone.localdate()).exclude(
                status__in=["done", "cancelled"]
            )
        return qs

    class Meta:
        model = ActionTask
        fields = ["status", "assignee", "action_plan", "priority", "meeting", "decision", "direction"]
