"""Modèles action_plans — version bêta CODIR."""
from django.db import models
from django.utils import timezone

from apps.common.enums import ActionPlanStatus, ActionTaskStatus, Priority
from core.models import TenantAwareModel


class ActionPlan(TenantAwareModel):
    # ⚠ Historiquement OneToOneField (1 décision = 1 plan max). Migré en
    # ForeignKey + null=True pour autoriser :
    #   - plusieurs plans par décision (court terme + moyen terme, etc.)
    #   - plans standalone sans décision parente
    # `related_name="action_plans"` (pluriel) — `decision.action_plans.all()`.
    decision = models.ForeignKey(
        "decisions.Decision",
        on_delete=models.CASCADE,
        related_name="action_plans",
        null=True, blank=True,
    )
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)
    owner = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="action_plans_owned",
    )
    start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=ActionPlanStatus.choices,
        default=ActionPlanStatus.OPEN, db_index=True,
    )
    progress_percent = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status"])]

    def recompute_progress(self):
        qs = self.tasks.all()
        total = qs.count()
        if total == 0:
            self.progress_percent = 0
            return
        done = qs.filter(status=ActionTaskStatus.DONE).count()
        self.progress_percent = int(round(done * 100 / total))


class ActionTask(TenantAwareModel):
    action_plan = models.ForeignKey(ActionPlan, on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.CASCADE, related_name="subtasks",
    )
    # Numéro d'ordre intra-plan (incrémenté automatiquement à la création).
    # Permet d'afficher et de trier les tâches selon la séquence métier.
    order = models.PositiveIntegerField(
        default=0, db_index=True,
        help_text="Numéro d'ordre intra-plan d'action. 0 = non assigné (auto à la création).",
    )
    title = models.CharField(max_length=300)
    description_md = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(
        max_length=20, choices=ActionTaskStatus.choices,
        default=ActionTaskStatus.TODO, db_index=True,
    )

    # Responsable principal (lead) — celui qui reçoit les rappels overdue
    assignee = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tasks_assigned",
        help_text="Responsable principal (lead). Pour les co-responsables, utiliser co_assignees.",
    )
    # Co-responsables : participants additionnels qui ont droit de modification
    co_assignees = models.ManyToManyField(
        "accounts.User", blank=True, related_name="tasks_co_assigned",
        help_text="Co-responsables (équipiers). Le 'assignee' principal reste le lead.",
    )

    due_date = models.DateField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    progress_percent = models.PositiveSmallIntegerField(default=0)
    effort_estimate_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    effort_actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        # Tri primaire par order intra-plan, puis échéance, puis création.
        ordering = ["action_plan", "order", "due_date", "created_at"]
        indexes = [
            models.Index(fields=["action_plan", "status"]),
            models.Index(fields=["action_plan", "order"]),
            models.Index(fields=["assignee", "due_date"]),
            models.Index(fields=["organization", "status", "due_date"]),
        ]

    @property
    def is_overdue(self) -> bool:
        if self.due_date is None:
            return False
        if self.status in {ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED}:
            return False
        return self.due_date < timezone.localdate()


class ActionComment(TenantAwareModel):
    task = models.ForeignKey(
        ActionTask, null=True, blank=True,
        on_delete=models.CASCADE, related_name="comments",
    )
    action_plan = models.ForeignKey(
        ActionPlan, null=True, blank=True,
        on_delete=models.CASCADE, related_name="comments",
    )
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body_md = models.TextField()

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["task", "created_at"])]


class ActionEvidence(TenantAwareModel):
    """Preuve d'exécution attachée à une tâche."""

    task = models.ForeignKey(ActionTask, on_delete=models.CASCADE, related_name="evidence")
    document = models.ForeignKey(
        "documents.Document", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="action_evidence",
    )
    url = models.URLField(blank=True)
    description = models.CharField(max_length=400, blank=True)
    submitted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="evidence_submitted",
    )
