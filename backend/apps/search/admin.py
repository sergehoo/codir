"""Admin — meta-index recherche : suggestions, recherches sauvegardées."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import SavedSearch, SearchIndexConfig, SearchSuggestion


@admin.register(SearchSuggestion)
class SearchSuggestionAdmin(TenantAwareAdmin):
    list_display = ("text", "hit_count", "last_seen_at", "organization")
    list_filter = ("organization",)
    search_fields = ("text",)
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at", "last_seen_at")


@admin.register(SavedSearch)
class SavedSearchAdmin(TenantAwareAdmin):
    list_display = ("name", "user", "is_alert", "alert_frequency", "updated_at", "organization")
    list_filter = ("is_alert", "alert_frequency", "organization")
    search_fields = ("name", "user__email")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SearchIndexConfig)
class SearchIndexConfigAdmin(TenantAwareAdmin):
    list_display = ("model_label", "opensearch_index", "mapping_version",
                    "is_active", "organization")
    list_filter = ("is_active", "organization")
    search_fields = ("model_label", "opensearch_index")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")
