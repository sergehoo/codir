"""Apps analytics — cubes pré-agrégés et prévisions."""
from django.db import models

from core.models import TenantAwareModel


class KPICubeDaily(TenantAwareModel):
    """Pré-agrégat journalier d'un KPI par direction (et subsidiary)."""

    kpi = models.ForeignKey("kpis.KPI", on_delete=models.CASCADE, related_name="cube_daily")
    subsidiary = models.ForeignKey("organizations.Subsidiary", null=True, blank=True, on_delete=models.CASCADE)
    direction = models.ForeignKey("governance.Direction", null=True, blank=True, on_delete=models.CASCADE)
    date = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        unique_together = [("kpi", "subsidiary", "direction", "date")]
        indexes = [models.Index(fields=["kpi", "date"])]


class DecisionCubeMonthly(TenantAwareModel):
    direction = models.ForeignKey("governance.Direction", null=True, blank=True, on_delete=models.CASCADE)
    month = models.DateField()
    status = models.CharField(max_length=20)
    count = models.PositiveIntegerField(default=0)
    total_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        unique_together = [("organization", "direction", "month", "status")]


class MeetingCubeWeekly(TenantAwareModel):
    codir = models.ForeignKey("codir.CodirInstance", on_delete=models.CASCADE)
    week_start = models.DateField()
    meetings_count = models.PositiveIntegerField(default=0)
    avg_duration_minutes = models.PositiveIntegerField(default=0)
    avg_attendance_pct = models.PositiveSmallIntegerField(default=0)
    decisions_count = models.PositiveIntegerField(default=0)


class Forecast(TenantAwareModel):
    ALGOS = [("prophet", "Prophet"), ("neural", "NeuralProphet"), ("arima", "ARIMA"), ("manual", "Manuel")]
    kpi = models.ForeignKey("kpis.KPI", on_delete=models.CASCADE, related_name="forecasts")
    algorithm = models.CharField(max_length=20, choices=ALGOS, default="prophet")
    horizon_periods = models.PositiveSmallIntegerField()
    forecast_json = models.JSONField()
    mape = models.FloatField(null=True, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)
