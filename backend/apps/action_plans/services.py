"""Services métier — action_plans."""
from django.db import transaction
from django.utils import timezone

from apps.common.enums import ActionPlanStatus, ActionTaskStatus
from apps.common.exceptions import TransitionNotAllowed

from .models import ActionComment, ActionEvidence, ActionPlan, ActionTask


@transaction.atomic
def create_task(*, action_plan: ActionPlan, data: dict) -> ActionTask:
    task = ActionTask.unscoped.create(
        organization=action_plan.organization, action_plan=action_plan, **data,
    )
    _recompute_plan_status(action_plan)
    return task


@transaction.atomic
def update_progress(*, task: ActionTask, progress_percent: int, status: str | None = None, actor=None) -> ActionTask:
    if progress_percent < 0 or progress_percent > 100:
        raise TransitionNotAllowed(detail="progress_percent doit être entre 0 et 100.")
    task.progress_percent = progress_percent
    if status:
        task.status = status
    if task.started_at is None and progress_percent > 0:
        task.started_at = timezone.now()
        if task.status == ActionTaskStatus.TODO:
            task.status = ActionTaskStatus.IN_PROGRESS
    if progress_percent == 100:
        task.status = ActionTaskStatus.DONE
        task.completed_at = timezone.now()
    task.save()
    _recompute_plan_status(task.action_plan)
    return task


class TaskArchiveError(Exception):
    """Levée quand on tente d'archiver une tâche non terminée à 100%."""


@transaction.atomic
def complete_task(*, task: ActionTask, actor=None, force: bool = False) -> ActionTask:
    """Archive (= terminée à 100%) une tâche.

    Une tâche ne peut être archivée que si elle est déjà à 100% de progression.
    Le flag ``force=True`` (réservé staff/exec) court-circuite cette protection.

    Raises:
        TaskArchiveError: si progress < 100 et force=False.
    """
    if not force and task.progress_percent < 100:
        raise TaskArchiveError(
            f"La tâche doit être à 100% pour être archivée "
            f"(progression actuelle : {task.progress_percent}%)."
        )
    task.status = ActionTaskStatus.DONE
    task.progress_percent = 100
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "progress_percent", "completed_at", "updated_at"])
    _recompute_plan_status(task.action_plan)
    return task


@transaction.atomic
def add_evidence(*, task: ActionTask, document=None, url: str = "", description: str = "", submitted_by=None) -> ActionEvidence:
    return ActionEvidence.unscoped.create(
        organization=task.organization, task=task,
        document=document, url=url, description=description,
        submitted_by=submitted_by,
    )


@transaction.atomic
def delegate_task(*, task: ActionTask, new_assignee, by_user, note: str = "") -> ActionTask:
    """Délègue / transfère une tâche à un autre membre.

    - Met à jour l'assignee
    - Ajoute un commentaire système traçable
    - Notifie le nouvel assigné (via signal post_save sur ActionTask déjà branché
      sur task_assigned ; on déclenche aussi un événement spécifique).
    """
    if task.status in {ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED}:
        raise TransitionNotAllowed(
            detail="Tâche déjà clôturée — impossible de la déléguer."
        )
    if new_assignee is None:
        raise TransitionNotAllowed(detail="Nouvel assigné requis.")
    if task.assignee_id == new_assignee.id:
        return task

    previous = task.assignee
    task.assignee = new_assignee
    task.save(update_fields=["assignee", "updated_at"])

    # Commentaire système éditorial
    prev_label = previous.get_full_name() if previous else "non assigné"
    new_label = new_assignee.get_full_name() or new_assignee.email
    body = f"_Tâche déléguée_ : **{prev_label}** → **{new_label}**"
    if note:
        body += f"\n\n> {note}"
    ActionComment.unscoped.create(
        organization=task.organization,
        task=task, author=by_user, body_md=body,
    )

    # Notifications nouveau + ancien responsable
    try:
        from apps.notifications.services import send_task_delegated_notification
        send_task_delegated_notification(
            task=task, old_assignee=previous, new_assignee=new_assignee,
            by_user=by_user, note=note,
        )
    except Exception:  # noqa: BLE001 — best effort
        pass

    # Audit
    try:
        from apps.audit_logs.services import log as audit_log
        audit_log(
            action="updated", target=task, actor=by_user,
            description=f"Tâche déléguée à {new_label}",
            diff={"assignee": {"before": str(previous.id) if previous else None,
                                "after": str(new_assignee.id)}},
        )
    except Exception:  # noqa: BLE001
        pass

    return task


@transaction.atomic
def postpone_task(*, task: ActionTask, new_due_date, by_user, reason: str = "") -> ActionTask:
    """Reporte l'échéance d'une tâche."""
    if task.status == ActionTaskStatus.DONE:
        raise TransitionNotAllowed(detail="Tâche déjà clôturée.")
    previous = task.due_date
    task.due_date = new_due_date
    # Si elle était overdue, on la repasse à in_progress / todo
    if task.status == ActionTaskStatus.OVERDUE:
        task.status = ActionTaskStatus.IN_PROGRESS if task.progress_percent > 0 else ActionTaskStatus.TODO
    task.save(update_fields=["due_date", "status", "updated_at"])

    note = f"_Échéance reportée_ : ~~{previous}~~ → **{new_due_date}**"
    if reason:
        note += f"\n\n> {reason}"
    ActionComment.unscoped.create(
        organization=task.organization, task=task,
        author=by_user, body_md=note,
    )
    return task


@transaction.atomic
def cancel_task(*, task: ActionTask, by_user, reason: str = "") -> ActionTask:
    task.status = ActionTaskStatus.CANCELLED
    task.save(update_fields=["status", "updated_at"])
    if reason:
        ActionComment.unscoped.create(
            organization=task.organization, task=task,
            author=by_user, body_md=f"_Tâche annulée_ — {reason}",
        )
    _recompute_plan_status(task.action_plan)
    return task


@transaction.atomic
def assign_task(*, task: ActionTask, assignee, assigned_by=None) -> ActionTask:
    """Assigne une tâche (création initiale ou réassignation simple).

    Si la tâche avait déjà un assignee différent, déclenche la délégation.
    """
    if assignee is None:
        raise TransitionNotAllowed(detail="Assigné requis.")
    if task.assignee_id == assignee.id:
        return task
    if task.assignee_id and task.assignee_id != assignee.id:
        # → délégation
        return delegate_task(task=task, new_assignee=assignee, by_user=assigned_by)

    task.assignee = assignee
    task.save(update_fields=["assignee", "updated_at"])
    try:
        from apps.notifications.services import send_task_assigned_notification
        send_task_assigned_notification(task=task, by_user=assigned_by)
    except Exception:  # noqa: BLE001
        pass
    return task


def mark_task_overdue(task: ActionTask) -> ActionTask:
    """Bascule en OVERDUE + notifie. Idempotent."""
    if task.status in (ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED, ActionTaskStatus.OVERDUE):
        return task
    task.status = ActionTaskStatus.OVERDUE
    task.save(update_fields=["status", "updated_at"])
    try:
        from apps.notifications.services import notify_task_overdue
        notify_task_overdue(task=task)
    except Exception:  # noqa: BLE001
        pass
    return task


def get_user_open_tasks(user, organization=None):
    """Toutes les tâches ouvertes (TODO / IN_PROGRESS / BLOCKED / OVERDUE) d'un user."""
    qs = ActionTask.unscoped.filter(
        assignee=user,
        status__in=[
            ActionTaskStatus.TODO, ActionTaskStatus.IN_PROGRESS,
            ActionTaskStatus.BLOCKED, ActionTaskStatus.OVERDUE,
        ],
    ).select_related("action_plan", "action_plan__decision")
    if organization is not None:
        qs = qs.filter(organization=organization)
    return qs.order_by("due_date", "-priority")


def get_manager_branch_tasks_summary(*, manager, organization=None, subsidiary=None, direction=None):
    """Résumé des tâches du périmètre d'un manager (filiale et/ou direction).

    Retourne un dict prêt pour le template manager_summary.
    """
    today = timezone.localdate()

    base = ActionTask.unscoped.exclude(
        status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED],
    )
    if organization is not None:
        base = base.filter(organization=organization)

    if subsidiary is not None:
        base = base.filter(action_plan__decision__direction__subsidiary=subsidiary)
    if direction is not None:
        base = base.filter(action_plan__decision__direction=direction)

    open_qs = base.select_related("assignee", "action_plan", "action_plan__decision")
    open_count = open_qs.count()
    overdue = open_qs.filter(due_date__lt=today).count()
    blocked = open_qs.filter(status=ActionTaskStatus.BLOCKED).count()

    # Critiques = priorité CRITICAL ou tâches HIGH en retard
    from apps.common.enums import Priority
    critical = open_qs.filter(priority__in=[Priority.CRITICAL, Priority.HIGH]).count()

    # Tâches top
    top_tasks = list(open_qs.order_by("due_date")[:10].values(
        "id", "title", "due_date", "status", "priority",
        "assignee__first_name", "assignee__last_name",
    ))

    # Décisions non exécutées dans le périmètre
    from apps.decisions.models import Decision
    from apps.common.enums import DecisionStatus
    dec_qs = Decision.unscoped.exclude(
        status__in=[DecisionStatus.COMPLETED, DecisionStatus.CANCELLED],
    )
    if organization is not None:
        dec_qs = dec_qs.filter(organization=organization)
    if subsidiary is not None:
        dec_qs = dec_qs.filter(direction__subsidiary=subsidiary)
    if direction is not None:
        dec_qs = dec_qs.filter(direction=direction)
    decisions_pending = dec_qs.count()

    # Avancement moyen
    plans = ActionPlan.unscoped.exclude(status=ActionPlanStatus.CANCELLED)
    if organization is not None:
        plans = plans.filter(organization=organization)
    if subsidiary is not None:
        plans = plans.filter(decision__direction__subsidiary=subsidiary)
    if direction is not None:
        plans = plans.filter(decision__direction=direction)
    progress_avg = 0
    if plans.exists():
        progress_avg = int(
            sum(p.progress_percent for p in plans) / max(plans.count(), 1)
        )

    return {
        "open": open_count, "overdue": overdue,
        "blocked": blocked, "critical": critical,
        "decisions_pending": decisions_pending,
        "progress_avg": progress_avg,
        "top_tasks": top_tasks,
    }


def resolve_plan_subsidiary(plan: ActionPlan):
    """Retourne la filiale d'un plan via la chaîne plan → decision → direction → subsidiary."""
    try:
        d = plan.decision
        direction = getattr(d, "direction", None)
        if direction and direction.subsidiary_id:
            return direction.subsidiary
    except Exception:  # noqa: BLE001
        return None
    return None


def user_subsidiary_ids(user, organization=None) -> set:
    """Set des subsidiary_id auxquels appartient `user` (via memberships → directions)."""
    from apps.accounts.models import Membership
    qs = Membership.unscoped.filter(user=user, is_active=True)
    if organization is not None:
        qs = qs.filter(organization=organization)
    ids: set = set()
    for m in qs.prefetch_related("directions"):
        for d in m.directions.all():
            if d.subsidiary_id:
                ids.add(d.subsidiary_id)
    return ids


def user_can_add_tasks_to_plan(user, plan: ActionPlan) -> bool:
    """Un user peut ajouter des tâches à un plan si :
    - il est owner du plan, OU
    - il appartient à la même filiale que le plan, OU
    - le plan n'a pas de filiale rattachée (cas Groupe).
    Les superusers passent toujours.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    if plan.owner_id and plan.owner_id == user.id:
        return True
    sub = resolve_plan_subsidiary(plan)
    if sub is None:
        return True  # plan Groupe : tous les membres peuvent
    return sub.id in user_subsidiary_ids(user, organization=plan.organization)


def _recompute_plan_status(plan: ActionPlan):
    plan.recompute_progress()
    qs = plan.tasks.all()
    if qs.count() == 0:
        plan.status = ActionPlanStatus.OPEN
    elif all(t.status == ActionTaskStatus.DONE for t in qs):
        plan.status = ActionPlanStatus.COMPLETED
        plan.actual_end_date = timezone.localdate()
    elif any(t.status == ActionTaskStatus.IN_PROGRESS for t in qs):
        plan.status = ActionPlanStatus.IN_PROGRESS
    plan.save(update_fields=["status", "progress_percent", "actual_end_date", "updated_at"])
