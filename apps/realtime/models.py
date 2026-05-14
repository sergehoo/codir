"""Apps realtime — présence (persisté optionnel), documents collaboratifs Yjs."""
from django.db import models

from core.models import TenantAwareModel


class CollaborationDoc(TenantAwareModel):
    """Binaire Yjs représentant l'état partagé d'un document collaboratif."""

    scope_type = models.CharField(max_length=40, help_text="meeting.note / agenda.note / document.annotation")
    scope_id = models.UUIDField()
    state_vector = models.BinaryField(null=True, blank=True)
    updates_blob = models.BinaryField(null=True, blank=True)
    last_updated_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("organization", "scope_type", "scope_id")]


class PresenceLog(TenantAwareModel):
    """Trace optionnelle d'activité (analytics) — la présence vivante est en Redis."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    scope = models.CharField(max_length=120)
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "scope", "joined_at"])]
