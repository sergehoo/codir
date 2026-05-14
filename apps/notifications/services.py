"""Services notifications — création, envoi, anti-doublon, ciblage manager.

Conception :
- L'API publique reste `notify(...)` (rétrocompatible avec l'existant).
- Les helpers spécifiques (task_assigned, task_delegated, daily_reminder,
  manager_summary, due_soon, overdue) délèguent à `notify` + render template.
- L'envoi email est asynchrone via Celery (tasks.send_notification_email).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    Notification, NotificationChannel, NotificationEvent,
    NotificationLevel, NotificationLog, NotificationPreference,
    NotificationPriority, NotificationStatus, ReminderTimeSlot,
    ReminderType, TaskReminderLog,
)


# ─── Préférences ──────────────────────────────────────────────

def get_or_create_preference(user, organization=None) -> NotificationPreference:
    """Retourne (et crée si absent) les préférences d'un utilisateur."""
    org = organization
    if org is None:
        m = user.memberships.filter(is_active=True).first()
        org = m.organization if m else None
    if org is None:
        raise ValueError("Impossible de déterminer l'organisation pour les préférences.")
    pref, _ = NotificationPreference.unscoped.get_or_create(
        user=user, defaults={"organization": org},
    )
    return pref


_EVENT_TO_PREF_FIELD = {
    NotificationEvent.TASK_ASSIGNED: "task_assignment_email",
    NotificationEvent.TASK_DELEGATED: "task_delegation_email",
    NotificationEvent.TASK_REMINDER: "daily_task_reminder",
    NotificationEvent.TASK_DUE_SOON: "due_soon_alert",
    NotificationEvent.TASK_DEADLINE: "due_soon_alert",
    NotificationEvent.TASK_OVERDUE: "overdue_alert",
    NotificationEvent.MANAGER_DAILY_SUMMARY: "manager_summary",
    NotificationEvent.DECISION_ASSIGNED: "decision_alerts",
    NotificationEvent.DECISION_APPROVED: "decision_alerts",
    NotificationEvent.DECISION_DEADLINE: "decision_alerts",
    NotificationEvent.DECISION_ACTION_DELAY: "decision_alerts",
    NotificationEvent.MEETING_INVITED: "meeting_alerts",
    NotificationEvent.MEETING_REMINDER: "meeting_alerts",
    NotificationEvent.MEETING_STARTED: "meeting_alerts",
    NotificationEvent.MEETING_COMPLETED: "meeting_alerts",
    NotificationEvent.AGENDA_VALIDATED: "meeting_alerts",
}


def should_send_notification(user, event: str, channel: str = NotificationChannel.EMAIL) -> bool:
    """Vérifie les préférences utilisateur — true par défaut si pas de pref."""
    try:
        pref = NotificationPreference.unscoped.filter(user=user).first()
    except Exception:  # noqa: BLE001
        pref = None
    if pref is None:
        return True
    channel_map = {
        NotificationChannel.EMAIL: pref.email_enabled,
        NotificationChannel.INTERNAL: pref.internal_enabled,
        NotificationChannel.SMS: pref.sms_enabled,
        NotificationChannel.WHATSAPP: pref.whatsapp_enabled,
        NotificationChannel.PUSH: pref.push_enabled,
    }
    if not channel_map.get(channel, True):
        return False
    field = _EVENT_TO_PREF_FIELD.get(event)
    if field and not getattr(pref, field, True):
        return False
    return True


# ─── Anti-doublon rappels ─────────────────────────────────────

def slot_now() -> str:
    now = timezone.localtime()
    return ReminderTimeSlot.MORNING if now.hour < 12 else ReminderTimeSlot.AFTERNOON


def prevent_duplicate_reminder(
    *, user, task=None, reminder_type: str,
    reminder_date: date | None = None,
    time_slot: str | None = None,
    channel: str = NotificationChannel.EMAIL,
) -> tuple[TaskReminderLog | None, bool]:
    """Crée un log de rappel — retourne (log, created)."""
    reminder_date = reminder_date or timezone.localdate()
    time_slot = time_slot or slot_now()
    try:
        with transaction.atomic():
            log = TaskReminderLog.objects.create(
                user=user, task=task,
                reminder_type=reminder_type, reminder_date=reminder_date,
                time_slot=time_slot, channel=channel,
                status=NotificationStatus.SENT,
                sent_at=timezone.now(),
            )
            return log, True
    except IntegrityError:
        return None, False


# ─── API publique ─────────────────────────────────────────────

@transaction.atomic
def notify(
    *, organization, recipient, event: str, title: str, body: str = "",
    level: str = NotificationLevel.INFO,
    priority: str = NotificationPriority.NORMAL,
    channel: str = NotificationChannel.INTERNAL,
    link_url: str = "", action_url: str = "",
    target=None, subsidiary=None, direction=None,
    metadata: dict | None = None,
    send_email: bool = False,
    email_template: str | None = None,
    email_context: dict | None = None,
    check_preference: bool = True,
) -> Notification | None:
    """Crée une notif interne + (optionnel) déclenche l'email Celery."""
    if check_preference and not should_send_notification(recipient, event, NotificationChannel.INTERNAL):
        return None

    target_type = ContentType.objects.get_for_model(target.__class__) if target is not None else None
    target_id = str(target.pk) if target is not None else ""

    n = Notification.unscoped.create(
        organization=organization, recipient=recipient,
        subsidiary=subsidiary, direction=direction,
        event=event, title=title, body=body, level=level,
        priority=priority, channel=channel,
        link_url=link_url, action_url=action_url or link_url,
        target_type=target_type, target_id=target_id,
        metadata=metadata or {},
        status=NotificationStatus.PENDING,
    )

    if send_email and recipient.email and should_send_notification(recipient, event, NotificationChannel.EMAIL):
        if email_template or email_context:
            md = n.metadata or {}
            md["email_template"] = email_template or ""
            md["email_context"] = email_context or {}
            n.metadata = md
            n.save(update_fields=["metadata"])
        from .tasks import send_notification_email
        send_notification_email.delay(str(n.id))

    return n


def notify_many(*, organization, recipients: Iterable, **kwargs):
    return [notify(organization=organization, recipient=u, **kwargs) for u in recipients if u]


# ─── Helpers spécialisés ──────────────────────────────────────

def _task_context(task) -> dict:
    plan = task.action_plan
    decision = getattr(plan, "decision", None)
    return {
        "task": {
            "id": str(task.id), "title": task.title,
            "priority": task.priority, "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "progress_percent": task.progress_percent,
        },
        "plan": {"id": str(plan.id), "title": plan.title},
        "decision": ({
            "id": str(decision.id), "ref": getattr(decision, "ref", ""),
            "title": decision.title,
        } if decision else None),
        "action_url": f"/action-plans/{plan.id}",
    }


def send_task_assigned_notification(*, task, by_user=None):
    if not task.assignee:
        return None
    return notify(
        organization=task.organization,
        recipient=task.assignee,
        event=NotificationEvent.TASK_ASSIGNED,
        level=NotificationLevel.INFO,
        priority=_priority_from_task(task),
        channel=NotificationChannel.EMAIL,
        title=f"Nouvelle tâche assignée : {task.title}",
        body=(f"Vous avez été assigné à la tâche **{task.title}**.\n"
              f"Échéance : {task.due_date or '—'}"),
        target=task,
        link_url=f"/action-plans/{task.action_plan_id}",
        action_url=f"/action-plans/{task.action_plan_id}",
        send_email=True,
        email_template="task_assigned",
        email_context=_task_context(task) | {"assigned_by": _user_label(by_user)},
    )


def send_task_delegated_notification(*, task, old_assignee, new_assignee, by_user=None, note: str = ""):
    results = []
    if new_assignee:
        results.append(notify(
            organization=task.organization,
            recipient=new_assignee,
            event=NotificationEvent.TASK_DELEGATED,
            level=NotificationLevel.INFO,
            priority=_priority_from_task(task),
            channel=NotificationChannel.EMAIL,
            title=f"Tâche déléguée : {task.title}",
            body=f"Cette tâche vous a été transférée par {_user_label(by_user)}.",
            target=task,
            link_url=f"/action-plans/{task.action_plan_id}",
            send_email=True,
            email_template="task_delegated",
            email_context=_task_context(task) | {
                "old_assignee": _user_label(old_assignee),
                "new_assignee": _user_label(new_assignee),
                "delegated_by": _user_label(by_user),
                "note": note, "is_recipient_new": True,
            },
        ))
    if old_assignee and old_assignee != new_assignee:
        results.append(notify(
            organization=task.organization,
            recipient=old_assignee,
            event=NotificationEvent.TASK_DELEGATED,
            level=NotificationLevel.INFO,
            channel=NotificationChannel.INTERNAL,
            title=f"Tâche transférée : {task.title}",
            body=f"La tâche a été transférée à {_user_label(new_assignee)}.",
            target=task,
            link_url=f"/action-plans/{task.action_plan_id}",
            send_email=False,
        ))
    return results


def send_user_task_reminder(*, user, organization, tasks, time_slot: str | None = None):
    if not tasks:
        return None
    today = timezone.localdate()
    slot = time_slot or slot_now()
    _, created = prevent_duplicate_reminder(
        user=user, task=None,
        reminder_type=ReminderType.DAILY_USER,
        reminder_date=today, time_slot=slot,
    )
    if not created:
        return None
    ctx = _build_user_reminder_context(user, tasks)
    return notify(
        organization=organization, recipient=user,
        event=NotificationEvent.TASK_REMINDER,
        level=NotificationLevel.INFO,
        priority=NotificationPriority.NORMAL,
        channel=NotificationChannel.EMAIL,
        title="Vos tâches CODIR du jour",
        body=f"{ctx['total']} tâche(s) ouverte(s) — {ctx['overdue']} en retard.",
        link_url="/my-tasks", action_url="/my-tasks",
        metadata={"slot": slot},
        send_email=True,
        email_template="daily_user_reminder",
        email_context=ctx,
    )


def send_manager_branch_summary(*, manager, organization, subsidiary=None, direction=None, summary: dict, time_slot: str | None = None):
    today = timezone.localdate()
    slot = time_slot or slot_now()
    _, created = prevent_duplicate_reminder(
        user=manager, task=None,
        reminder_type=ReminderType.MANAGER_SUMMARY,
        reminder_date=today, time_slot=slot,
    )
    if not created:
        return None
    label = getattr(subsidiary, "name", None) or getattr(direction, "name", None) or "périmètre"
    return notify(
        organization=organization, recipient=manager,
        event=NotificationEvent.MANAGER_DAILY_SUMMARY,
        level=NotificationLevel.INFO,
        priority=NotificationPriority.HIGH,
        channel=NotificationChannel.EMAIL,
        subsidiary=subsidiary, direction=direction,
        title=f"Résumé CODIR — {label}",
        body=(f"{summary.get('open', 0)} tâche(s) ouverte(s) — "
              f"{summary.get('overdue', 0)} en retard."),
        link_url="/dashboard", action_url="/dashboard",
        metadata={"slot": slot, "summary": summary},
        send_email=True,
        email_template="manager_summary",
        email_context={"manager": _user_label(manager), "label": label, **summary},
    )


def notify_task_due_soon(*, task):
    if not task.assignee:
        return None
    today = timezone.localdate()
    _, created = prevent_duplicate_reminder(
        user=task.assignee, task=task,
        reminder_type=ReminderType.DUE_SOON,
        reminder_date=today, time_slot=ReminderTimeSlot.ANYTIME,
    )
    if not created:
        return None
    return notify(
        organization=task.organization, recipient=task.assignee,
        event=NotificationEvent.TASK_DUE_SOON,
        level=NotificationLevel.WARNING,
        priority=NotificationPriority.HIGH,
        channel=NotificationChannel.EMAIL,
        title=f"Échéance proche : {task.title}",
        body=f"Échéance : {task.due_date}",
        target=task, link_url=f"/action-plans/{task.action_plan_id}",
        send_email=True,
        email_template="task_due_soon",
        email_context=_task_context(task),
    )


def notify_task_overdue(*, task):
    if not task.assignee:
        return None
    today = timezone.localdate()
    _, created = prevent_duplicate_reminder(
        user=task.assignee, task=task,
        reminder_type=ReminderType.OVERDUE,
        reminder_date=today, time_slot=ReminderTimeSlot.ANYTIME,
    )
    if not created:
        return None
    return notify(
        organization=task.organization, recipient=task.assignee,
        event=NotificationEvent.TASK_OVERDUE,
        level=NotificationLevel.DANGER,
        priority=NotificationPriority.CRITICAL,
        channel=NotificationChannel.EMAIL,
        title=f"Tâche en retard : {task.title}",
        body=f"Échéance dépassée : {task.due_date}",
        target=task, link_url=f"/action-plans/{task.action_plan_id}",
        send_email=True,
        email_template="task_overdue",
        email_context=_task_context(task),
    )


# ─── Helpers internes ─────────────────────────────────────────

def _priority_from_task(task) -> str:
    from apps.common.enums import Priority
    return {
        Priority.CRITICAL: NotificationPriority.CRITICAL,
        Priority.HIGH: NotificationPriority.HIGH,
        Priority.MEDIUM: NotificationPriority.NORMAL,
        Priority.LOW: NotificationPriority.LOW,
    }.get(task.priority, NotificationPriority.NORMAL)


def _user_label(user) -> str:
    if not user:
        return "système"
    return user.get_full_name() or user.email


def _build_user_reminder_context(user, tasks) -> dict:
    from apps.common.enums import ActionTaskStatus
    today = timezone.localdate()
    soon = today + timedelta(days=2)
    buckets = {"todo": [], "in_progress": [], "blocked": [], "overdue": [], "due_soon": []}
    for t in tasks:
        if t.status in (ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED):
            continue
        if t.due_date and t.due_date < today:
            buckets["overdue"].append(t)
        elif t.due_date and t.due_date <= soon:
            buckets["due_soon"].append(t)
        if t.status == ActionTaskStatus.TODO:
            buckets["todo"].append(t)
        elif t.status == ActionTaskStatus.IN_PROGRESS:
            buckets["in_progress"].append(t)
        elif t.status == ActionTaskStatus.BLOCKED:
            buckets["blocked"].append(t)

    def _ser(t):
        return {
            "id": str(t.id), "title": t.title,
            "priority": t.priority, "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "progress_percent": t.progress_percent,
            "plan_id": str(t.action_plan_id),
            "plan_title": getattr(t.action_plan, "title", ""),
        }

    return {
        "user": _user_label(user),
        "today": today.isoformat(),
        "total": sum(len(v) for v in buckets.values()),
        "overdue": len(buckets["overdue"]),
        "due_soon": len(buckets["due_soon"]),
        "buckets": {k: [_ser(t) for t in v[:20]] for k, v in buckets.items()},
        "action_url": "/my-tasks",
    }


def create_internal_notification(*, organization, recipient, event, title, body="", **kwargs):
    return notify(
        organization=organization, recipient=recipient, event=event,
        title=title, body=body,
        channel=NotificationChannel.INTERNAL, send_email=False, **kwargs,
    )


def log_transport(*, notification, provider, channel, status_code="", response="", error=""):
    return NotificationLog.objects.create(
        notification=notification, provider=provider, channel=channel,
        status_code=str(status_code), response=response or "",
        error_message=error or "",
    )


def mark_email_sent(notification: Notification):
    notification.email_sent_at = timezone.now()
    notification.sent_at = notification.sent_at or timezone.now()
    notification.status = NotificationStatus.SENT
    notification.save(update_fields=["email_sent_at", "sent_at", "status", "updated_at"])


def render_email(template_base: str, context: dict) -> tuple[str, str]:
    """Rendu HTML + texte d'un template email — fallback simple si absent."""
    try:
        html = render_to_string(f"notifications/emails/{template_base}.html", context)
    except Exception:  # noqa: BLE001
        html = ""
    try:
        text = render_to_string(f"notifications/emails/{template_base}.txt", context)
    except Exception:  # noqa: BLE001
        text = ""
    return html, text
