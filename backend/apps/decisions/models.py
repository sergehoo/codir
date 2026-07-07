"""Modèles decisions — version bêta CODIR."""
from django.db import models

from apps.common.enums import DecisionStatus, ImpactLevel, Priority
from core.models import TenantAwareModel


class DecisionCategory(TenantAwareModel):
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#2563eb")
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Decision(TenantAwareModel):
    """Décision actée en CODIR."""

    ref = models.CharField(max_length=20, db_index=True, help_text="DEC-YYYY-NNNN — auto")
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)

    meeting = models.ForeignKey(
        "meetings.Meeting", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions",
    )
    agenda_item = models.ForeignKey(
        "agendas.AgendaItem", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions",
    )
    subsidiary = models.ForeignKey(
        "organizations.Subsidiary", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions",
        help_text="Filiale concernée par la décision (optionnel, cas Groupe si vide).",
    )
    direction = models.ForeignKey(
        "governance.Direction", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions",
    )
    category = models.ForeignKey(
        DecisionCategory, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions",
    )

    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    impact = models.CharField(max_length=10, choices=ImpactLevel.choices, default=ImpactLevel.MEDIUM)
    status = models.CharField(
        max_length=20, choices=DecisionStatus.choices,
        default=DecisionStatus.PROPOSED, db_index=True,
    )

    responsible = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions_responsible",
    )
    deadline = models.DateField(null=True, blank=True, db_index=True)

    is_confidential = models.BooleanField(default=False)

    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions_approved",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions_created",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("organization", "ref")]
        indexes = [
            models.Index(fields=["organization", "status", "deadline"]),
            models.Index(fields=["organization", "responsible"]),
            models.Index(fields=["organization", "priority"]),
        ]

    def __str__(self):
        return f"{self.ref} — {self.title}"


class DecisionHistory(TenantAwareModel):
    """Trace de chaque changement métier (statut, responsable, échéance)."""

    decision = models.ForeignKey(Decision, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decision_history_entries",
    )
    event = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["decision", "-created_at"])]


class DecisionComment(TenantAwareModel):
    decision = models.ForeignKey(Decision, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body_md = models.TextField()

    class Meta:
        ordering = ["created_at"]
