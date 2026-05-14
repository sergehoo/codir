"""Services métier — decisions."""
from datetime import date

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.common.enums import DecisionStatus
from apps.common.exceptions import TransitionNotAllowed

from .models import Decision, DecisionHistory


def _next_ref(organization) -> str:
    year = timezone.now().year
    prefix = f"DEC-{year}-"
    last = (
        Decision.unscoped
        .filter(organization=organization, ref__startswith=prefix)
        .aggregate(Max("ref"))["ref__max"]
    )
    n = 1
    if last:
        try:
            n = int(last.rsplit("-", 1)[-1]) + 1
        except ValueError:
            n = 1
    return f"{prefix}{n:04d}"


@transaction.atomic
def create_decision(*, organization, created_by, data: dict) -> Decision:
    data = dict(data)
    data.setdefault("ref", _next_ref(organization))
    decision = Decision.unscoped.create(
        organization=organization, created_by=created_by, **data,
    )
    DecisionHistory.unscoped.create(
        organization=organization, decision=decision, actor=created_by,
        event="created", description=f"Décision créée : {decision.title}",
    )
    return decision


@transaction.atomic
def approve_decision(*, decision: Decision, approver) -> Decision:
    if decision.status not in {DecisionStatus.PROPOSED, DecisionStatus.POSTPONED}:
        raise TransitionNotAllowed(
            detail=f"Une décision en statut '{decision.status}' ne peut être validée."
        )
    decision.status = DecisionStatus.APPROVED
    decision.approved_at = timezone.now()
    decision.approved_by = approver
    decision.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=approver,
        event="approved", description="Décision validée",
    )
    return decision


@transaction.atomic
def start_decision(*, decision: Decision, actor) -> Decision:
    if decision.status != DecisionStatus.APPROVED:
        raise TransitionNotAllowed(detail="Décision non validée — exécution impossible.")
    decision.status = DecisionStatus.IN_PROGRESS
    decision.save(update_fields=["status", "updated_at"])
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=actor,
        event="started", description="Exécution démarrée",
    )
    return decision


@transaction.atomic
def complete_decision(*, decision: Decision, actor) -> Decision:
    if decision.status not in {DecisionStatus.IN_PROGRESS, DecisionStatus.APPROVED}:
        raise TransitionNotAllowed(detail="Statut incompatible.")
    decision.status = DecisionStatus.COMPLETED
    decision.completed_at = timezone.now()
    decision.save(update_fields=["status", "completed_at", "updated_at"])
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=actor,
        event="completed", description="Décision réalisée",
    )
    return decision


@transaction.atomic
def cancel_decision(*, decision: Decision, actor, reason: str = "") -> Decision:
    decision.status = DecisionStatus.CANCELLED
    decision.save(update_fields=["status", "updated_at"])
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=actor,
        event="cancelled", description=reason or "Décision annulée",
    )
    return decision


@transaction.atomic
def postpone_decision(*, decision: Decision, actor, new_deadline: date | None = None) -> Decision:
    decision.status = DecisionStatus.POSTPONED
    if new_deadline:
        decision.deadline = new_deadline
    decision.save(update_fields=["status", "deadline", "updated_at"])
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=actor,
        event="postponed", description=f"Reportée → {new_deadline}",
        metadata={"new_deadline": new_deadline.isoformat() if new_deadline else None},
    )
    return decision


@transaction.atomic
def convert_to_action_plan(*, decision: Decision, actor, title: str = "",
                           description_md: str = "", target_end_date=None, tasks: list[dict] | None = None):
    """Crée un ActionPlan + tâches optionnelles depuis une décision validée."""
    from apps.action_plans.models import ActionPlan, ActionTask

    if decision.status not in {DecisionStatus.APPROVED, DecisionStatus.IN_PROGRESS}:
        raise TransitionNotAllowed(
            detail="La décision doit être validée pour générer un plan d'action."
        )
    if hasattr(decision, "action_plan"):
        return decision.action_plan

    plan = ActionPlan.unscoped.create(
        organization=decision.organization,
        decision=decision,
        title=title or f"Plan — {decision.title}",
        description_md=description_md or decision.description_md,
        owner=decision.responsible,
        start_date=timezone.localdate(),
        target_end_date=target_end_date or decision.deadline,
    )
    for t in (tasks or []):
        ActionTask.unscoped.create(
            organization=decision.organization, action_plan=plan, **t,
        )
    DecisionHistory.unscoped.create(
        organization=decision.organization, decision=decision, actor=actor,
        event="action_plan_created", description=f"Plan d'action {plan.id} créé",
    )
    return plan
