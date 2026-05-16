"""Apps dashboards — configuration, widgets, layout, EPI score."""
from django.db import models

from core.models import TenantAwareModel


class EpiScoreSnapshot(TenantAwareModel):
    """Snapshot quotidien de l'Executive Performance Index pour une organisation.

    Stocké en daily snapshot pour permettre :
      - Sparkline d'évolution sur 90 jours
      - Alerte de chute > N points
      - Audit du score (transparence : on garde les composantes et les counts bruts)

    Le score global est dans ``overall_score`` (0-100). Les 4 sous-scores
    composent ce score selon les pondérations définies dans le service.
    """

    date = models.DateField(db_index=True)
    overall_score = models.PositiveSmallIntegerField(help_text="EPI final 0-100")

    # ── Sous-scores 0-100 ──
    completion_score = models.PositiveSmallIntegerField(default=0)
    punctuality_score = models.PositiveSmallIntegerField(default=0)
    velocity_score = models.PositiveSmallIntegerField(default=0)
    quorum_score = models.PositiveSmallIntegerField(default=0)
    overdue_penalty = models.PositiveSmallIntegerField(default=0, help_text="Points retirés (0-30)")

    # ── Compteurs bruts (transparence + audit) ──
    tasks_total = models.PositiveIntegerField(default=0)
    tasks_done = models.PositiveIntegerField(default=0)
    tasks_done_on_time = models.PositiveIntegerField(default=0)
    tasks_overdue = models.PositiveIntegerField(default=0)
    avg_days_to_close = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    meetings_total = models.PositiveIntegerField(default=0)
    meetings_quorum_reached = models.PositiveIntegerField(default=0)

    # ── Métadonnées d'alerte ──
    drop_alert_sent = models.BooleanField(default=False, help_text="True si alerte chute envoyée")
    drop_vs_previous = models.SmallIntegerField(default=0, help_text="Delta vs jour J-1 (peut être négatif)")

    class Meta:
        unique_together = [("organization", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["organization", "-date"]),
        ]

    def __str__(self):
        return f"EPI {self.organization.slug} @ {self.date} = {self.overall_score}"


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
