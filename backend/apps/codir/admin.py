"""Admin — CODIR instances et chartes."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import CodirCharter, CodirInstance


@admin.register(CodirInstance)
class CodirInstanceAdmin(TenantAwareAdmin):
    list_display = ("name", "subsidiary", "frequency", "default_day_of_week",
                    "default_time", "default_duration_minutes",
                    "quorum_min_members", "chairperson", "is_active")
    list_filter = ("frequency", "is_active", "subsidiary")
    search_fields = ("name", "description", "subsidiary__name")
    autocomplete_fields = ("subsidiary", "chairperson", "secretary", "organization")
    filter_horizontal = ("permanent_members",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identification", {"fields": ("name", "description", "subsidiary", "organization")}),
        ("Cadence", {
            "fields": ("frequency", "default_day_of_week", "default_time", "default_duration_minutes"),
        }),
        ("Gouvernance", {
            "fields": ("chairperson", "secretary", "permanent_members", "quorum_min_members"),
        }),
        ("État", {"fields": ("is_active",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(CodirCharter)
class CodirCharterAdmin(TenantAwareAdmin):
    list_display = ("codir", "version", "approved_at", "updated_at")
    search_fields = ("codir__name", "content_md")
    autocomplete_fields = ("codir", "organization")
    readonly_fields = ("created_at", "updated_at", "approved_at")
