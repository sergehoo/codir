"""Apps dashboards — configuration, widgets, layout."""
from django.db import models

from core.models import TenantAwareModel


class Dashboard(TenantAwareModel):
    PERSONA = [
        ("dg", "DG"), ("daf", "DAF"), ("drh", "DRH"), ("dsi", "DSI"),
        ("dt", "Directeur Technique"), ("dc", "Directeur Commercial"),
        ("pmo", "PMO"), ("audit", "Audit"), ("custom", "Personnalisé"),
    ]

    owner = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="dashboards")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    target_persona = models.CharField(max_length=20, choices=PERSONA, default="custom")
    is_template = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    layout_json = models.JSONField(default=list, blank=True, help_text="gridstack layout")

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["organization", "owner"]),
            models.Index(fields=["organization", "is_template"]),
        ]


class DashboardWidget(TenantAwareModel):
    WIDGET_TYPE = [
        ("kpi_card", "KPI Card"),
        ("line_chart", "Line Chart"),
        ("bar_chart", "Bar Chart"),
        ("pie_chart", "Pie Chart"),
        ("heatmap", "Heatmap"),
        ("radar", "Radar"),
        ("table", "Tableau"),
        ("text", "Texte / Markdown"),
        ("feed", "Feed d'activité"),
        ("ai_briefing", "Briefing IA"),
        ("powerbi_embed", "Power BI Embed"),
    ]

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPE)
    title = models.CharField(max_length=120, blank=True)
    config = models.JSONField(default=dict, blank=True)
    data_source = models.JSONField(default=dict, blank=True)
    format = models.JSONField(default=dict, blank=True)
    thresholds = models.JSONField(default=dict, blank=True)
    position = models.JSONField(default=dict, blank=True)  # {x,y,w,h}
    order = models.PositiveIntegerField(default=0)
    refresh_interval_seconds = models.PositiveIntegerField(default=60)

    class Meta:
        ordering = ["dashboard", "order"]
