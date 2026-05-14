"""Modèles de base CODIR : TimestampedModel + TenantAwareModel."""
import uuid

from django.db import models

from core.managers.tenant import TenantManager


class TimestampedModel(models.Model):
    """Modèle abstrait avec id UUID + horodatages."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Soft delete : on garde la ligne en base mais on l'exclut par défaut."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class TenantAwareModel(TimestampedModel):
    """
    Base abstraite pour toute entité métier d'un tenant.
    Toute requête passe par TenantManager qui filtre automatiquement par
    `organization_id == current_tenant`.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    objects = TenantManager()
    unscoped = models.Manager()  # bypass volontaire (migrations, admin global)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["organization", "-created_at"])]
