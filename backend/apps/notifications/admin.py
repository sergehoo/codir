from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Notification


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
