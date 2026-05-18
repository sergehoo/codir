"""Admin — workflows : définitions, instances, transitions, approbations."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Approval, WorkflowDefinition, WorkflowInstance, WorkflowTransition


class WorkflowTransitionInline(admin.TabularInline):
    model = WorkflowTransition
    extra = 0
    fields = ("occurred_at", "code", "from_state", "to_state", "actor")
    readonly_fields = ("occurred_at",)
    autocomplete_fields = ("actor",)
    ordering = ("-occurred_at",)
    show_change_link = True


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(TenantAwareAdmin):
    list_display = ("code", "name", "version", "is_system",
                    "target_content_type", "organization")
    list_filter = ("is_system", "version", "organization")
    search_fields = ("code", "name", "description")
    autocomplete_fields = ("target_content_type", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(TenantAwareAdmin):
    list_display = ("definition", "current_state", "target_content_type",
                    "target_id", "updated_at", "organization")
    list_filter = ("current_state", "definition", "organization")
    search_fields = ("target_id", "definition__code", "definition__name")
    autocomplete_fields = ("definition", "target_content_type", "organization")
    readonly_fields = ("created_at", "updated_at")
    inlines = [WorkflowTransitionInline]


@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(TenantAwareAdmin):
    list_display = ("instance", "code", "from_state", "to_state",
                    "actor", "occurred_at")
    list_filter = ("from_state", "to_state", "organization")
    search_fields = ("code", "from_state", "to_state", "actor__email")
    autocomplete_fields = ("instance", "actor", "organization")
    readonly_fields = ("created_at", "updated_at", "occurred_at")
    date_hierarchy = "occurred_at"


@admin.register(Approval)
class ApprovalAdmin(TenantAwareAdmin):
    list_display = ("approver", "state", "status", "due_at",
                    "decided_at", "organization")
    list_filter = ("status", "state", "organization")
    search_fields = ("approver__email", "state", "comment")
    autocomplete_fields = ("instance", "approver", "organization")
    readonly_fields = ("created_at", "updated_at", "decided_at")
    date_hierarchy = "due_at"
