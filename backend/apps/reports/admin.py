"""Admin — templates de rapport, runs, plans d'envoi."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import ReportRun, ReportTemplate, ScheduledReport


@admin.register(ReportTemplate)
class ReportTemplateAdmin(TenantAwareAdmin):
    list_display = ("code", "name", "format", "is_system", "organization")
    list_filter = ("format", "is_system", "organization")
    search_fields = ("code", "name", "description")
    autocomplete_fields = ("template_file", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReportRun)
class ReportRunAdmin(TenantAwareAdmin):
    list_display = ("template", "status", "requested_by", "started_at",
                    "completed_at", "output_file")
    list_filter = ("status", "organization")
    search_fields = ("template__name", "template__code", "error", "requested_by__email")
    autocomplete_fields = ("template", "requested_by", "output_file", "organization")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at", "error")
    date_hierarchy = "created_at"


@admin.register(ScheduledReport)
class ScheduledReportAdmin(TenantAwareAdmin):
    list_display = ("template", "cron", "timezone", "is_active", "last_run_at", "organization")
    list_filter = ("is_active", "timezone", "organization")
    search_fields = ("template__name", "cron")
    autocomplete_fields = ("template", "organization")
    filter_horizontal = ("recipients",)
    readonly_fields = ("created_at", "updated_at", "last_run_at")
