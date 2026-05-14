from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_detail = UserMiniSerializer(source="actor", read_only=True)
    target_model = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_detail", "action",
            "target_model", "target_id", "target_repr",
            "description", "diff_json", "ip", "user_agent",
            "created_at",
        ]
        read_only_fields = fields

    def get_target_model(self, obj):
        if obj.target_type_id is None:
            return None
        return f"{obj.target_type.app_label}.{obj.target_type.model}"
