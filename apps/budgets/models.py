"""Apps budgets — budgets, lignes, scénarios, dépenses."""
from decimal import Decimal

from django.db import models

from core.models import TenantAwareModel


class BudgetStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    CONTROLLER_REVIEW = "controller_review", "Contrôle de gestion"
    CFO_REVIEW = "cfo_review", "DAF"
    BOARD_REVIEW = "board_review", "CODIR"
    APPROVED = "approved", "Approuvé"
    CLOSED = "closed", "Clôturé"


class Budget(TenantAwareModel):
    subsidiary = models.ForeignKey("organizations.Subsidiary", null=True, blank=True, on_delete=models.SET_NULL)
    year = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    currency = models.CharField(max_length=3, default="EUR")
    status = models.CharField(max_length=30, choices=BudgetStatus.choices, default=BudgetStatus.DRAFT)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("organization", "subsidiary", "year", "name")]
        ordering = ["-year", "name"]


class BudgetLine(TenantAwareModel):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=80, blank=True)
    direction = models.ForeignKey("governance.Direction", null=True, on_delete=models.SET_NULL, related_name="budget_lines")
    period = models.CharField(max_length=20, default="annual", choices=[
        ("annual", "Annuel"), ("h1", "S1"), ("h2", "S2"),
        ("q1", "T1"), ("q2", "T2"), ("q3", "T3"), ("q4", "T4"), ("monthly", "Mensuel"),
    ])
    planned_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    committed_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    spent_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)

    @property
    def variance(self):
        return self.planned_amount - self.spent_amount


class BudgetScenario(TenantAwareModel):
    """Simulation what-if."""

    base_budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="scenarios")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    deltas_json = models.JSONField(default=list, blank=True)
    projected_impact_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="draft")
    created_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)


class BudgetSpend(TenantAwareModel):
    SOURCE = [("manual", "Manuelle"), ("integration", "Intégration ERP")]

    budget_line = models.ForeignKey(BudgetLine, on_delete=models.CASCADE, related_name="spends")
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    vendor = models.CharField(max_length=200, blank=True)
    invoice_ref = models.CharField(max_length=80, blank=True)
    spent_on = models.DateField()
    description = models.TextField(blank=True)
    validated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=20, choices=SOURCE, default="manual")
    integration_external_id = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-spent_on"]
        indexes = [models.Index(fields=["budget_line", "-spent_on"])]
