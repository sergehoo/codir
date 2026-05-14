from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    Decision, DecisionCategory, DecisionComment, DecisionHistory,
)


class DecisionHistoryInline(admin.TabularInline):
    model = DecisionHistory
    extra = 0
    readonly_fields = ("event", "description", "actor", "metadata", "created_at")
    fields = ("created_at", "event", "actor", "description")
    can_delete = False
    ordering = ("-created_at",)


@admin.register(DecisionCategory)
class DecisionCategoryAdmin(TenantAwareAdmin):
    list_display = ("name", "organization", "color")
    search_fields = ("name",)
    autocomplete_fields = ("organization",)


@admin.register(Decision)
class DecisionAdmin(TenantAwareAdmin):
    list_display = (
        "ref", "title", "status", "priority", "impact",
        "responsible", "deadline", "is_confidential", "organization",
    )
    list_filter = ("status", "priority", "impact", "is_confidential", "organization", "category")
    search_fields = ("ref", "title", "description_md")
    autocomplete_fields = (
        "meeting", "agenda_item", "direction", "category",
        "responsible", "approved_by", "created_by", "organization",
    )
    readonly_fields = ("id", "ref", "created_at", "updated_at", "approved_at", "completed_at")
    inlines = [DecisionHistoryInline]
    date_hierarchy = "deadline"
    fieldsets = (
        ("Identité", {"fields": ("id", "ref", "title", "description_md", "organization")}),
        ("Contexte", {"fields": ("meeting", "agenda_item", "direction", "category")}),
        ("Classification", {"fields": ("priority", "impact", "is_confidential")}),
        ("État & échéances", {"fields": ("status", "deadline", "approved_at", "approved_by",
                                          "completed_at")}),
        ("Responsabilité", {"fields": ("responsible", "created_by")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(DecisionHistory)
class DecisionHistoryAdmin(TenantAwareAdmin):
    list_display = ("decision", "event", "actor", "created_at")
    list_filter = ("event",)
    search_fields = ("decision__ref", "decision__title", "event", "description")
    autocomplete_fields = ("decision", "actor")
    readonly_fields = ("decision", "event", "description", "actor", "metadata", "created_at", "updated_at")


@admin.register(DecisionComment)
class DecisionCommentAdmin(TenantAwareAdmin):
    list_display = ("decision", "author", "created_at")
    search_fields = ("decision__ref", "body_md")
    autocomplete_fields = ("decision", "author")
