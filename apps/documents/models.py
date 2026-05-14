"""Modèles documents — version bêta (upload simple + rattachement générique)."""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TenantAwareModel


class Document(TenantAwareModel):
    name = models.CharField(max_length=300)
    file = models.FileField(upload_to="documents/%Y/%m/")
    mime = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    is_confidential = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="documents_uploaded",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self):
        return self.name


class DocumentAttachment(TenantAwareModel):
    """Rattachement polymorphe (un document peut être lié à plusieurs objets)."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="attachments")
    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.CharField(max_length=80)
    target = GenericForeignKey("target_type", "target_id")
    label = models.CharField(max_length=120, blank=True)
    attached_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="attachments_made",
    )

    class Meta:
        unique_together = [("document", "target_type", "target_id")]
        indexes = [models.Index(fields=["target_type", "target_id"])]
