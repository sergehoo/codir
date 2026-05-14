"""Apps administration — paramétrage tenant, AI config, feature flags, plans, facturation."""
from django.db import models

from core.models import TenantAwareModel


class TenantSettings(TenantAwareModel):
    """Paramétrage central d'un tenant."""

    modules_enabled = models.JSONField(default=dict, blank=True)
    password_policy = models.JSONField(default=dict, blank=True)
    branding = models.JSONField(default=dict, blank=True)
    notification_defaults = models.JSONField(default=dict, blank=True)
    data_retention_days = models.PositiveIntegerField(default=1825)  # 5 ans
    audit_retention_days = models.PositiveIntegerField(default=1825)

    class Meta:
        verbose_name_plural = "Tenant settings"


class AIConfiguration(TenantAwareModel):
    default_provider = models.CharField(max_length=40, default="openai")
    providers = models.JSONField(default=dict, blank=True)
    capability_overrides = models.JSONField(default=dict, blank=True)
    sovereign_mode = models.BooleanField(default=False)
    max_monthly_spend_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data_residency = models.CharField(max_length=20, default="eu-west")
    zero_retention = models.BooleanField(default=False)
    blocked_terms = models.JSONField(default=list, blank=True)


class FeatureFlag(TenantAwareModel):
    """Feature flag par tenant (avec valeur globale optionnelle si organization NULL)."""

    key = models.SlugField(max_length=120)
    enabled = models.BooleanField(default=False)
    rollout_percent = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("organization", "key")]


class Plan(TenantAwareModel):
    """Référentiel de plans commerciaux."""

    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    monthly_price_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_price_eur = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    features = models.JSONField(default=list, blank=True)
    seat_limit = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class Invoice(TenantAwareModel):
    STATUS = [("draft", "Brouillon"), ("issued", "Émise"), ("paid", "Payée"), ("overdue", "En retard"), ("cancelled", "Annulée")]
    number = models.CharField(max_length=40, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    amount_excl_tax = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    stripe_invoice_id = models.CharField(max_length=120, blank=True)
    pdf_doc = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL)
