from django_filters import rest_framework as filters

from .models import Decision


class DecisionFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status")
    priority = filters.CharFilter(field_name="priority")
    impact = filters.CharFilter(field_name="impact")
    responsible = filters.UUIDFilter(field_name="responsible_id")
    direction = filters.UUIDFilter(field_name="direction_id")
    meeting = filters.UUIDFilter(field_name="meeting_id")
    deadline_before = filters.DateFilter(field_name="deadline", lookup_expr="lte")
    deadline_after = filters.DateFilter(field_name="deadline", lookup_expr="gte")
    is_confidential = filters.BooleanFilter(field_name="is_confidential")

    class Meta:
        model = Decision
        fields = ["status", "priority", "impact", "responsible", "direction", "meeting", "is_confidential"]
