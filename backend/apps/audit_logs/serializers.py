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


class AccessLogSerializer(serializers.Serializer):
    """Sérialise un évènement de connexion (succès ou échec) issu de django-axes.

    Source unifiée pour AccessLog (connexions réussies) et AccessAttempt (échecs).
    """
    kind = serializers.CharField()              # "success" | "failed"
    username = serializers.CharField()
    user_id = serializers.IntegerField(allow_null=True)
    user_full_name = serializers.CharField(allow_blank=True)
    ip_address = serializers.IPAddressField(allow_null=True)
    user_agent = serializers.CharField(allow_blank=True)
    path_info = serializers.CharField(allow_blank=True)
    attempt_time = serializers.DateTimeField()
    logout_time = serializers.DateTimeField(allow_null=True, required=False)
    failures_since_start = serializers.IntegerField(allow_null=True, required=False)
