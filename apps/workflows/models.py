"""Apps workflows — moteur générique de machine d'état + journal de transitions."""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TenantAwareModel


class WorkflowDefinition(TenantAwareModel):
    """Spécification déclarative d'un workflow (machine d'état)."""

    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    spec = models.JSONField(help_text="Définition DAG : initial_state, states, transitions")
    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("organization", "code", "version")]


class WorkflowInstance(TenantAwareModel):
    definition = models.ForeignKey(WorkflowDefinition, on_delete=models.PROTECT, related_name="instances")
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.UUIDField()
    target = GenericForeignKey("target_content_type", "target_id")
    current_state = models.CharField(max_length=60, db_index=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "definition", "current_state"]),
            models.Index(fields=["target_content_type", "target_id"]),
        ]


class WorkflowTransition(TenantAwareModel):
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name="transitions")
    code = models.CharField(max_length=60)
    from_state = models.CharField(max_length=60)
    to_state = models.CharField(max_length=60)
    actor = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["instance", "-occurred_at"])]


class Approval(TenantAwareModel):
    """Tâche d'approbation attachée à un état de workflow."""

    STATUS = [("pending", "En attente"), ("approved", "Approuvée"), ("rejected", "Rejetée"), ("escalated", "Escaladée")]

    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="approvals_requested")
    state = models.CharField(max_length=60)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    due_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
