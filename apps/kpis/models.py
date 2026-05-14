"""Apps kpis — définition, calcul, snapshots, alertes."""
from django.db import models

from core.models import TenantAwareModel


class KPICategory(models.TextChoices):
    FINANCIAL = "financial", "Financier"
    HR = "hr", "RH"
    OPERATIONS = "ops", "Opérations"
    IT = "it", "SI / Technique"
    RISK = "risk", "Risques"
    QUALITY = "quality", "Qualité"
    CUSTOMER = "customer", "Client / Commercial"
    ESG = "esg", "ESG / RSE"
    CUSTOM = "custom", "Personnalisé"


class KPIFrequency(models.TextChoices):
    REAL_TIME = "real_time", "Temps réel"
    HOURLY = "hourly", "Horaire"
    DAILY = "daily", "Quotidien"
    WEEKLY = "weekly", "Hebdomadaire"
    MONTHLY = "monthly", "Mensuel"
    QUARTERLY = "quarterly", "Trimestriel"


class KPI(TenantAwareModel):
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=KPICategory.choices, default=KPICategory.FINANCIAL)
    unit = models.CharField(max_length=20, default="€")  # € / % / count / days / score
    decimals = models.PositiveSmallIntegerField(default=2)

    target_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    target_direction = models.CharField(max_length=10, default="max", choices=[
        ("max", "Maximiser"), ("min", "Minimiser"), ("range", "Plage cible")
    ])
    warning_threshold = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    frequency = models.CharField(max_length=20, choices=KPIFrequency.choices, default=KPIFrequency.DAILY)
    formula = models.TextField(blank=True, help_text="DSL formule ou null si source via intégration")
    source_integration = models.ForeignKey("integrations.Integration", null=True, blank=True, on_delete=models.SET_NULL)

    owner = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="kpis_owned")
    consumers = models.ManyToManyField("governance.Direction", blank=True, related_name="kpis_consumed")

    is_active = models.BooleanField(default=True)
    last_calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("organization", "code")]
        ordering = ["category", "name"]
        indexes = [models.Index(fields=["organization", "category", "is_active"])]


class KPISnapshot(TenantAwareModel):
    """Valeur ponctuelle calculée d'un KPI sur une période donnée."""

    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name="snapshots")
    value = models.DecimalField(max_digits=18, decimal_places=4)
    formatted_value = models.CharField(max_length=40, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    breakdown_json = models.JSONField(default=dict, blank=True)
    method = models.CharField(max_length=40, default="formula")  # formula|integration|manual

    class Meta:
        ordering = ["-period_end"]
        indexes = [
            models.Index(fields=["kpi", "-period_end"]),
            models.Index(fields=["organization", "kpi", "-period_end"]),
        ]


class KPIAlert(TenantAwareModel):
    LEVEL = [("warning", "Warning"), ("critical", "Critical")]

    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name="alerts")
    snapshot = models.ForeignKey(KPISnapshot, on_delete=models.CASCADE)
    level = models.CharField(max_length=10, choices=LEVEL)
    message = models.TextField()
    ai_analysis = models.TextField(blank=True, help_text="Cause racine probable proposée par l'IA")
    acknowledged_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "level", "resolved_at"])]
