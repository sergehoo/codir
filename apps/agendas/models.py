"""Modèles agendas — version bêta CODIR."""
from django.db import models

from apps.common.enums import AgendaItemStatus, Priority
from core.models import TenantAwareModel


class Agenda(TenantAwareModel):
    """Ordre du jour rattaché à une réunion."""

    meeting = models.OneToOneField("meetings.Meeting", on_delete=models.CASCADE, related_name="agenda")
    is_validated = models.BooleanField(default=False, db_index=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="agendas_validated",
    )
    notes_md = models.TextField(blank=True)

    @property
    def items_count(self) -> int:
        return self.items.count()

    @property
    def total_estimated_minutes(self) -> int:
        return sum(i.estimated_duration_minutes for i in self.items.all())


class AgendaItem(TenantAwareModel):
    """Point à l'ordre du jour."""

    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveIntegerField(default=0, db_index=True)
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    estimated_duration_minutes = models.PositiveIntegerField(default=15)
    actual_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    responsible = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="agenda_items_owned",
    )
    status = models.CharField(
        max_length=20, choices=AgendaItemStatus.choices,
        default=AgendaItemStatus.PENDING, db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    discussion_notes_md = models.TextField(blank=True, help_text="Synthèse de la discussion")

    class Meta:
        ordering = ["agenda_id", "order"]
        indexes = [
            models.Index(fields=["agenda", "order"]),
            models.Index(fields=["organization", "status"]),
        ]


class AgendaItemComment(TenantAwareModel):
    item = models.ForeignKey(AgendaItem, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body_md = models.TextField()

    class Meta:
        ordering = ["created_at"]
