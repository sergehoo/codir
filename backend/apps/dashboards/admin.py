"""Admin — dashboards, widgets, snapshots EPI."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Dashboard, DashboardWidget, EpiScoreSnapshot


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = ("order", "widget_type", "title", "refresh_interval_seconds")
    ordering = ("order",)
    show_change_link = True


@admin.register(Dashboard)
class DashboardAdmin(TenantAwareAdmin):
    list_display = ("name", "owner", "target_persona", "is_template", "is_shared",
                    "updated_at", "organization")
    list_filter = ("target_persona", "is_template", "is_shared", "organization")
    search_fields = ("name", "description", "owner__email")
    autocomplete_fields = ("owner", "organization")
    readonly_fields = ("created_at", "updated_at")
    inlines = [DashboardWidgetInline]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(TenantAwareAdmin):
    list_display = ("title", "dashboard", "widget_type", "order",
                    "refresh_interval_seconds")
    list_filter = ("widget_type",)
    search_fields = ("title", "dashboard__name")
    autocomplete_fields = ("dashboard", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EpiScoreSnapshot)
class EpiScoreSnapshotAdmin(TenantAwareAdmin):
    list_display = ("date", "overall_score", "completion_score", "punctuality_score",
                    "velocity_score", "quorum_score", "overdue_penalty",
                    "drop_vs_previous", "drop_alert_sent", "organization")
    list_filter = ("drop_alert_sent", "organization", "date")
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization",)
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Snapshot", {"fields": ("organization", "date", "overall_score")}),
        ("Sous-scores 0-100", {
            "fields": ("completion_score", "punctuality_score",
                       "velocity_score", "quorum_score", "overdue_penalty"),
        }),
        ("Compteurs bruts", {
            "fields": ("tasks_total", "tasks_done", "tasks_done_on_time",
                       "tasks_overdue", "avg_days_to_close",
                       "meetings_total", "meetings_quorum_reached"),
        }),
        ("Alertes", {"fields": ("drop_alert_sent", "drop_vs_previous")}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
