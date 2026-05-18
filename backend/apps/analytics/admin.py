"""Admin — cubes pré-agrégés et prévisions analytics."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import DecisionCubeMonthly, Forecast, KPICubeDaily, MeetingCubeWeekly


@admin.register(KPICubeDaily)
class KPICubeDailyAdmin(TenantAwareAdmin):
    list_display = ("kpi", "date", "value", "direction", "subsidiary", "organization")
    list_filter = ("date", "organization")
    search_fields = ("kpi__code", "kpi__name")
    autocomplete_fields = ("kpi", "direction", "subsidiary", "organization")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")


@admin.register(DecisionCubeMonthly)
class DecisionCubeMonthlyAdmin(TenantAwareAdmin):
    list_display = ("month", "direction", "status", "count", "total_budget", "organization")
    list_filter = ("status", "organization")
    autocomplete_fields = ("direction", "organization")
    date_hierarchy = "month"
    readonly_fields = ("created_at", "updated_at")


@admin.register(MeetingCubeWeekly)
class MeetingCubeWeeklyAdmin(TenantAwareAdmin):
    list_display = ("codir", "week_start", "meetings_count", "avg_duration_minutes",
                    "avg_attendance_pct", "decisions_count")
    autocomplete_fields = ("codir", "organization")
    date_hierarchy = "week_start"
    readonly_fields = ("created_at", "updated_at")


@admin.register(Forecast)
class ForecastAdmin(TenantAwareAdmin):
    list_display = ("kpi", "algorithm", "horizon_periods", "mape", "computed_at")
    list_filter = ("algorithm",)
    search_fields = ("kpi__code", "kpi__name")
    autocomplete_fields = ("kpi", "organization")
    readonly_fields = ("created_at", "updated_at", "computed_at", "forecast_json")
