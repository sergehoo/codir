"""Tâches Celery — notifications, rappels & résumés.

Tâches périodiques (cf. CELERY_BEAT_SCHEDULE) :
- send_daily_task_reminders_task : 09h00 / 16h00 Africa/Abidjan
- send_manager_daily_summaries_task : 09h00 / 16h00 Africa/Abidjan
- detect_overdue_tasks_task : chaque heure
- send_due_soon_alerts_task : chaque matin 08h00
"""
from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import (
    Notification, NotificationChannel, NotificationStatus,
)
from .services import (
    get_or_create_preference, log_transport, mark_email_sent, render_email,
    send_user_task_reminder, send_manager_branch_summary,
    notify_task_due_soon, notify_task_overdue,
)


# ─── Email unitaire ───────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_notification_email(self, notification_id: str):
    """Envoi de l'email associé à une notification — idempotent."""
    n = Notification.unscoped.filter(id=notification_id).select_related("recipient").first()
    if not n or n.email_sent_at:
        return "skipped"
    if not n.recipient.email:
        return "no-email"

    md = n.metadata or {}
    template_base = md.get("email_template", "generic")
    context = md.get("email_context", {}) | {
        "title": n.title, "body": n.body,
        "recipient_email": n.recipient.email,
        "recipient_name": n.recipient.get_full_name() or n.recipient.email,
        "link_url": _absolute(n.action_url or n.link_url),
        "site_name": getattr(settings, "DEFAULT_SITE_NAME", "CODIR"),
    }
    html, text = render_email(template_base, context)

    subject = f"[CODIR] {n.title}"
    body_text = text or n.body or n.title
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

    msg = EmailMultiAlternatives(
        subject=subject, body=body_text,
        from_email=from_email, to=[n.recipient.email],
    )
    if html:
        msg.attach_alternative(html, "text/html")

    try:
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        n.failed_at = timezone.now()
        n.error_message = str(exc)[:1000]
        n.status = NotificationStatus.FAILED
        n.save(update_fields=["failed_at", "error_message", "status", "updated_at"])
        log_transport(
            notification=n, provider="smtp",
            channel=NotificationChannel.EMAIL,
            status_code="error", error=str(exc),
        )
        raise self.retry(exc=exc)

    mark_email_sent(n)
    log_transport(
        notification=n, provider="smtp",
        channel=NotificationChannel.EMAIL,
        status_code="sent",
    )
    return "sent"


# ─── Tâches périodiques (Celery Beat) ─────────────────────────

@shared_task
def send_daily_task_reminders_task():
    """Envoie un résumé des tâches en cours à chaque user ayant des tâches ouvertes."""
    from apps.accounts.models import User
    from apps.action_plans.services import get_user_open_tasks

    count = 0
    qs = User.objects.filter(is_active=True).exclude(email="")
    for user in qs:
        m = user.memberships.filter(is_active=True).first()
        if not m:
            continue
        try:
            get_or_create_preference(user, organization=m.organization)
        except Exception:  # noqa: BLE001
            continue
        tasks = list(get_user_open_tasks(user, organization=m.organization))
        if not tasks:
            continue
        result = send_user_task_reminder(
            user=user, organization=m.organization, tasks=tasks,
        )
        if result:
            count += 1
    return count


@shared_task
def send_manager_daily_summaries_task():
    """Envoie le résumé filiale/direction à chaque manager (Direction.head + DG)."""
    from apps.governance.models import Direction
    from apps.organizations.models import Subsidiary
    from apps.action_plans.services import get_manager_branch_tasks_summary

    sent = 0

    # 1) Managers de direction : Direction.head
    for direction in Direction.unscoped.filter(head__isnull=False).select_related("head", "subsidiary", "organization"):
        manager = direction.head
        if not manager or not manager.email:
            continue
        summary = get_manager_branch_tasks_summary(
            manager=manager, organization=direction.organization,
            direction=direction,
        )
        if summary["open"] == 0:
            continue
        result = send_manager_branch_summary(
            manager=manager, organization=direction.organization,
            direction=direction, subsidiary=direction.subsidiary,
            summary=summary,
        )
        if result:
            sent += 1

    # 2) DG de filiale : memberships avec is_owner=True
    from apps.accounts.models import Membership
    seen_managers = set()
    for ms in Membership.unscoped.filter(is_owner=True, is_active=True).select_related("user", "organization"):
        user = ms.user
        if not user.email or user.id in seen_managers:
            continue
        seen_managers.add(user.id)
        # Si le user a des directions, on en prend la 1re pour résoudre la filiale ;
        # sinon résumé groupe.
        d = ms.directions.select_related("subsidiary").first()
        subsidiary = d.subsidiary if d else None
        summary = get_manager_branch_tasks_summary(
            manager=user, organization=ms.organization,
            subsidiary=subsidiary,
        )
        if summary["open"] == 0:
            continue
        result = send_manager_branch_summary(
            manager=user, organization=ms.organization,
            subsidiary=subsidiary, summary=summary,
        )
        if result:
            sent += 1

    return sent


@shared_task
def detect_overdue_tasks_task():
    """Détecte les tâches dont l'échéance est passée → OVERDUE + notif."""
    from apps.action_plans.models import ActionTask
    from apps.action_plans.services import mark_task_overdue
    from apps.common.enums import ActionTaskStatus

    today = timezone.localdate()
    qs = ActionTask.unscoped.filter(
        due_date__lt=today,
    ).exclude(status__in=[
        ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED, ActionTaskStatus.OVERDUE,
    ]).select_related("assignee", "action_plan", "organization")

    count = 0
    for task in qs:
        mark_task_overdue(task)
        count += 1
    return count


@shared_task
def send_due_soon_alerts_task():
    """Alerte échéance J+1 / J+2 sur tâches ouvertes (1× par jour)."""
    from apps.action_plans.models import ActionTask
    from apps.common.enums import ActionTaskStatus

    today = timezone.localdate()
    horizon = today + timedelta(days=2)
    qs = ActionTask.unscoped.filter(
        due_date__gte=today, due_date__lte=horizon,
    ).exclude(status__in=[
        ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED,
    ]).select_related("assignee", "action_plan", "organization")

    sent = 0
    for task in qs:
        if notify_task_due_soon(task=task):
            sent += 1
    return sent


# ─── Helpers ──────────────────────────────────────────────────

def _absolute(url: str) -> str:
    """Ajoute le domaine frontend si absent."""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    base = getattr(settings, "FRONTEND_BASE_URL", "")
    if base and url.startswith("/"):
        return base.rstrip("/") + url
    return url
