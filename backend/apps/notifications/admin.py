from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    Notification, NotificationLog, NotificationPreference, TaskReminderLog,
)


@admin.register(Notification)
class NotificationAdmin(TenantAwareAdmin):
    list_display = ("title", "recipient", "event", "level",
                    "seen_at", "email_sent_at", "created_at", "organization")
    list_filter = ("event", "level", "organization")
    search_fields = ("title", "body", "recipient__email")
    autocomplete_fields = ("recipient", "organization")
    readonly_fields = ("created_at", "updated_at", "email_sent_at",
                       "target_type", "target_id")
    date_hierarchy = "created_at"
    fieldsets = (
        ("Destinataire", {"fields": ("recipient", "organization")}),
        ("Contenu", {"fields": ("event", "level", "title", "body", "link_url")}),
        ("Cible", {"fields": ("target_type", "target_id")}),
        ("Lecture / envoi", {"fields": ("seen_at", "email_sent_at")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(TenantAwareAdmin):
    """Préférences utilisateur — canal email/sms/push + toggles par événement."""

    list_display = (
        "user", "email_enabled", "internal_enabled",
        "task_assignment_email", "daily_task_reminder",
        "due_soon_alert", "overdue_alert",
        "organization",
    )
    list_filter = (
        "email_enabled", "internal_enabled",
        "task_assignment_email", "daily_task_reminder",
        "due_soon_alert", "overdue_alert",
        "organization",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Utilisateur", {"fields": ("user", "organization", "locale")}),
        ("Canaux", {
            "fields": (
                "email_enabled", "internal_enabled",
                "sms_enabled", "whatsapp_enabled", "push_enabled",
            ),
            "description": "Canaux activés globalement pour cet utilisateur. "
                           "Si email_enabled est False, AUCUN email ne part, "
                           "quelle que soit la valeur des toggles ci-dessous.",
        }),
        ("Événements (emails)", {
            "fields": (
                "task_assignment_email", "task_delegation_email",
                "daily_task_reminder", "manager_summary",
                "due_soon_alert", "overdue_alert",
                "decision_alerts", "meeting_alerts",
            ),
            "description": "Désactiver un toggle empêche l'email correspondant. "
                           "La notification interne reste créée.",
        }),
        ("Heures de silence", {
            "fields": ("quiet_hours_start", "quiet_hours_end"),
            "classes": ("collapse",),
        }),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Trace technique des envois (provider, status, erreurs SMTP)."""

    list_display = ("notification", "provider", "channel", "status_code",
                    "short_error", "created_at")
    list_filter = ("channel", "provider", "status_code")
    search_fields = ("notification__title", "error_message", "response", "status_code")
    autocomplete_fields = ("notification",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Erreur (extrait)")
    def short_error(self, obj):
        if not obj.error_message:
            return "—"
        return (obj.error_message[:80] + "…") if len(obj.error_message) > 80 else obj.error_message


@admin.register(TaskReminderLog)
class TaskReminderLogAdmin(admin.ModelAdmin):
    """Anti-doublon des rappels périodiques (overdue / due_soon / daily)."""

    list_display = ("user", "task", "reminder_type", "reminder_date",
                    "time_slot", "channel", "status", "sent_at")
    list_filter = ("reminder_type", "time_slot", "channel", "status", "reminder_date")
    search_fields = ("user__email", "task__title")
    autocomplete_fields = ("user", "task")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "reminder_date"
    ordering = ("-reminder_date", "-created_at")
