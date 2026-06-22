"""Serializers DRF — notifications et préférences."""
from rest_framework import serializers

from .models import Notification, NotificationLog, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    subsidiary_name = serializers.CharField(source="subsidiary.name", read_only=True)
    direction_name = serializers.CharField(source="direction.name", read_only=True)
    is_read = serializers.SerializerMethodField()

    # Multi-org : on expose le nom + logo + couleur de l'organisation
    # propriétaire de la notification afin que le frontend puisse afficher
    # un mini-avatar à côté de chaque notif pour les users multi-orgs.
    organization_id = serializers.UUIDField(source="organization.id", read_only=True, allow_null=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True, allow_null=True)
    organization_logo = serializers.CharField(source="organization.logo", read_only=True, allow_null=True)
    organization_primary_color = serializers.CharField(
        source="organization.primary_color", read_only=True, allow_null=True
    )

    class Meta:
        model = Notification
        fields = [
            "id", "event", "level", "priority", "channel", "status",
            "title", "body", "link_url", "action_url",
            "subsidiary", "subsidiary_name", "direction", "direction_name",
            "target_type", "target_id",
            "sent_at", "seen_at", "read_at", "failed_at",
            "email_sent_at", "error_message",
            "metadata", "is_read", "created_at",
            # Branding org propriétaire (multi-org)
            "organization_id", "organization_name",
            "organization_logo", "organization_primary_color",
        ]
        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.seen_at is not None


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            # Canaux
            "email_enabled", "internal_enabled", "sms_enabled",
            "whatsapp_enabled", "push_enabled",
            # Événements
            "task_assignment_email", "task_delegation_email",
            "daily_task_reminder", "manager_summary",
            "due_soon_alert", "overdue_alert",
            "decision_alerts", "meeting_alerts",
            # Agent IA proactif (Lot 2)
            "proactive_agent_enabled",
            # Heures de silence
            "quiet_hours_start", "quiet_hours_end",
            "locale",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ["id", "provider", "channel", "status_code", "response", "error_message", "created_at"]
        read_only_fields = fields
