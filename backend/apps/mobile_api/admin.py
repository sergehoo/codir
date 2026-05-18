"""Admin — mobile devices + sync cursors."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import MobileDevice, MobileSyncCursor


@admin.register(MobileDevice)
class MobileDeviceAdmin(TenantAwareAdmin):
    list_display = ("user", "platform", "device_model", "os_version",
                    "app_version", "locale", "is_active", "last_seen_at")
    list_filter = ("platform", "is_active", "locale", "organization")
    search_fields = ("user__email", "device_model", "push_token")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    fieldsets = (
        ("Utilisateur", {"fields": ("user", "organization")}),
        ("Device", {"fields": ("platform", "device_model", "os_version",
                               "app_version", "locale")}),
        ("Push", {"fields": ("push_token", "is_active", "last_seen_at")}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(MobileSyncCursor)
class MobileSyncCursorAdmin(TenantAwareAdmin):
    list_display = ("user", "resource_type", "cursor", "last_sync_at", "organization")
    list_filter = ("resource_type", "organization")
    search_fields = ("user__email", "resource_type")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at", "updated_at", "last_sync_at")
