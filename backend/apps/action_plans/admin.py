from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    ActionComment, ActionEvidence, ActionPlan, ActionTask,
)


class ActionTaskInline(admin.TabularInline):
    model = ActionTask
    fk_name = "action_plan"
    extra = 0
    autocomplete_fields = ("assignee", "parent")
    fields = ("title", "priority", "status", "assignee", "due_date", "progress_percent")


@admin.register(ActionPlan)
class ActionPlanAdmin(TenantAwareAdmin):
    list_display = ("title", "decision", "status", "progress_percent",
                    "owner", "target_end_date", "organization")
    list_filter = ("status", "organization")
    search_fields = ("title", "description_md", "decision__ref", "decision__title")
    autocomplete_fields = ("decision", "owner", "organization")
    readonly_fields = ("progress_percent", "created_at", "updated_at")
    inlines = [ActionTaskInline]


@admin.register(ActionTask)
class ActionTaskAdmin(TenantAwareAdmin):
    list_display = ("title", "action_plan", "status", "priority",
                    "assignee", "due_date", "progress_percent")
    list_filter = ("status", "priority")
    search_fields = ("title", "description_md")
    autocomplete_fields = ("action_plan", "parent", "assignee")
    readonly_fields = ("started_at", "completed_at", "created_at", "updated_at")
    date_hierarchy = "due_date"


@admin.register(ActionComment)
class ActionCommentAdmin(TenantAwareAdmin):
    list_display = ("task", "action_plan", "author", "created_at")
    search_fields = ("body_md",)
    autocomplete_fields = ("task", "action_plan", "author")


@admin.register(ActionEvidence)
class ActionEvidenceAdmin(TenantAwareAdmin):
    list_display = ("task", "submitted_by", "description", "created_at")
    search_fields = ("description", "url")
    autocomplete_fields = ("task", "document", "submitted_by")
