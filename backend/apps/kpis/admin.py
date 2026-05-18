"""Admin — KPIs : définitions, snapshots, alertes."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import KPI, KPIAlert, KPISnapshot


@admin.register(KPI)
class KPIAdmin(TenantAwareAdmin):
    list_display = ("code", "name", "category", "unit", "target_value",
                    "target_direction", "frequency", "owner", "is_active",
                    "last_calculated_at", "organization")
    list_filter = ("category", "frequency", "target_direction", "is_active", "organization")
    search_fields = ("code", "name", "description", "formula")
    autocomplete_fields = ("owner", "source_integration", "organization")
    filter_horizontal = ("consumers",)
    readonly_fields = ("created_at", "updated_at", "last_calculated_at")
    fieldsets = (
        ("Identification", {"fields": ("code", "name", "description", "category", "unit", "decimals")}),
        ("Cibles & seuils", {
            "fields": ("target_value", "target_direction",
                       "warning_threshold", "critical_threshold"),
        }),
        ("Calcul", {
            "fields": ("frequency", "formula", "source_integration"),
        }),
        ("Gouvernance", {
            "fields": ("owner", "consumers", "is_active", "organization"),
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at", "last_calculated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(KPISnapshot)
class KPISnapshotAdmin(TenantAwareAdmin):
    list_display = ("kpi", "value", "formatted_value", "period_start", "period_end",
                    "method", "organization")
    list_filter = ("method", "organization")
    search_fields = ("kpi__code", "kpi__name")
    autocomplete_fields = ("kpi", "organization")
    date_hierarchy = "period_end"
    readonly_fields = ("created_at", "updated_at", "breakdown_json")


@admin.register(KPIAlert)
class KPIAlertAdmin(TenantAwareAdmin):
    list_display = ("kpi", "level", "acknowledged_by", "acknowledged_at",
                    "resolved_at", "created_at")
    list_filter = ("level", "organization")
    search_fields = ("kpi__code", "kpi__name", "message")
    autocomplete_fields = ("kpi", "snapshot", "acknowledged_by", "organization")
    readonly_fields = ("created_at", "updated_at", "ai_analysis")
    date_hierarchy = "created_at"
