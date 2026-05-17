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
    fields = ("order", "title", "priority", "status", "assignee", "due_date", "progress_percent")
    ordering = ("order", "due_date")


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
    list_display = (
        "order_display", "title", "action_plan", "status", "priority",
        "assignee", "co_assignees_count", "due_date", "progress_percent",
    )
    list_display_links = ("order_display", "title")
    list_filter = ("status", "priority", "action_plan")
    list_editable = ()  # order pourrait être ici mais conflit avec list_display_links
    search_fields = ("title", "description_md", "assignee__email", "assignee__last_name")
    autocomplete_fields = ("action_plan", "parent", "assignee")
    filter_horizontal = ("co_assignees",)
    readonly_fields = ("started_at", "completed_at", "created_at", "updated_at")
    date_hierarchy = "due_date"
    ordering = ("action_plan", "order", "due_date")
    fieldsets = (
        ("Identification", {
            "fields": ("action_plan", "parent", "order", "title", "description_md"),
        }),
        ("Affectation", {
            "fields": ("assignee", "co_assignees"),
            "description": "Le lead reçoit les rappels automatiques. "
                           "Les co-responsables peuvent modifier la tâche mais "
                           "n'ont pas de rappels auto.",
        }),
        ("Planification", {
            "fields": ("priority", "status", "due_date", "progress_percent",
                       "effort_estimate_hours", "effort_actual_hours"),
        }),
        ("Audit", {
            "fields": ("started_at", "completed_at", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="N°", ordering="order")
    def order_display(self, obj):
        return f"#{obj.order:02d}" if obj.order else "—"

    @admin.display(description="Co-resp.")
    def co_assignees_count(self, obj):
        count = obj.co_assignees.count()
        return f"+{count}" if count else "—"


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
