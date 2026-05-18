"""Admin — collaboration temps réel (CRDT Yjs + traces présence)."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import CollaborationDoc, PresenceLog


@admin.register(CollaborationDoc)
class CollaborationDocAdmin(TenantAwareAdmin):
    list_display = ("scope_type", "scope_id", "last_updated_by",
                    "updated_at", "organization")
    list_filter = ("scope_type", "organization")
    search_fields = ("scope_type", "scope_id")
    autocomplete_fields = ("last_updated_by", "organization")
    # Blobs binaires Yjs : pas affichables en clair
    exclude = ("state_vector", "updates_blob")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PresenceLog)
class PresenceLogAdmin(TenantAwareAdmin):
    list_display = ("user", "scope", "joined_at", "left_at", "organization")
    list_filter = ("organization",)
    search_fields = ("user__email", "scope")
    autocomplete_fields = ("user", "organization")
    date_hierarchy = "joined_at"
    readonly_fields = ("created_at", "updated_at")
