"""Apps risks — cartographie, scoring, mitigation, incidents, conformité."""
from django.db import models

from core.models import TenantAwareModel


class RiskCategory(models.TextChoices):
    OPERATIONAL = "operational", "Opérationnel"
    FINANCIAL = "financial", "Financier"
    CYBER = "cyber", "Cyber"
    LEGAL = "legal", "Juridique"
    STRATEGIC = "strategic", "Stratégique"
    HR = "hr", "RH"
    REPUTATIONAL = "reputational", "Réputationnel"
    COMPLIANCE = "compliance", "Conformité"
    ESG = "esg", "ESG"


class RiskStatus(models.TextChoices):
    IDENTIFIED = "identified", "Identifié"
    ASSESSED = "assessed", "Évalué"
    MITIGATION_PLANNED = "mitigation_planned", "Plan de mitigation"
    MITIGATING = "mitigating", "Mitigation en cours"
    MITIGATED = "mitigated", "Atténué"
    REALIZED = "realized", "Réalisé (incident)"
    CLOSED = "closed", "Clos"


class Risk(TenantAwareModel):
    ref = models.CharField(max_length=20, db_index=True, help_text="RSK-YYYY-NNNN")
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=RiskCategory.choices)
    impact = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    probability = models.PositiveSmallIntegerField(default=1, help_text="1-5")
    severity = models.PositiveSmallIntegerField(default=1, help_text="impact × probability")
    status = models.CharField(max_length=30, choices=RiskStatus.choices, default=RiskStatus.IDENTIFIED)
    owner = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="risks_owned")
    direction = models.ForeignKey("governance.Direction", null=True, on_delete=models.SET_NULL, related_name="risks")
    detected_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-severity", "-created_at"]
        unique_together = [("organization", "ref")]
        indexes = [
            models.Index(fields=["organization", "status", "severity"]),
            models.Index(fields=["organization", "category"]),
        ]

    def save(self, *args, **kwargs):
        self.severity = self.impact * self.probability
        super().save(*args, **kwargs)


class RiskAssessment(TenantAwareModel):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="assessments")
    assessor = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    impact = models.PositiveSmallIntegerField()
    probability = models.PositiveSmallIntegerField()
    comments = models.TextField(blank=True)
    review_date = models.DateField()


class RiskMitigation(TenantAwareModel):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="mitigations")
    title = models.CharField(max_length=250)
    description_md = models.TextField(blank=True)
    action_plan = models.ForeignKey("action_plans.ActionPlan", null=True, blank=True, on_delete=models.SET_NULL)
    target_residual_impact = models.PositiveSmallIntegerField(null=True, blank=True)
    target_residual_probability = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, default="planned")


class Incident(TenantAwareModel):
    SEVERITY = [("low", "Mineur"), ("medium", "Modéré"), ("high", "Majeur"), ("critical", "Critique")]
    risk = models.ForeignKey(Risk, null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY, default="medium")
    detected_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    impact_financial = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    lessons_learned_md = models.TextField(blank=True)


class Compliance(TenantAwareModel):
    STATUS = [("compliant", "Conforme"), ("partial", "Partiel"), ("non_compliant", "Non conforme"), ("under_review", "En audit")]
    framework = models.CharField(max_length=80, help_text="RGPD, ISO 27001, HDS, BCE, etc.")
    requirement = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=STATUS, default="under_review")
    next_audit = models.DateField(null=True, blank=True)
    responsible = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    evidence_doc = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL)
