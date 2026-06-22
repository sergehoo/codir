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
    send_user_task_reminder, send_user_weekly_digest,
    send_manager_branch_summary,
    notify_task_due_soon, notify_task_overdue,
)


# ─── Email unitaire ───────────────────────────────────────────

# ─── Événements considérés "digest" — peuvent porter Precedence: bulk
# (résumés quotidiens, rappels périodiques). Les notifs transactionnelles
# NE DOIVENT JAMAIS porter ce header, sinon Gmail les classe en Promotions.
_DIGEST_EVENTS = {
    "manager_daily_summary",
    "task_reminder",
}


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
    site_name = getattr(settings, "DEFAULT_SITE_NAME", "CODIR")

    # ⚡ Multi-org : injection auto du branding de l'organisation propriétaire
    # de la notification dans le contexte du template. base.html utilise
    # `org_name`, `org_logo`, `org_primary_color`, `org_secondary_color`.
    org = n.organization
    org_branding = {
        "org_name":            getattr(org, "name", "") or "",
        "org_logo":            getattr(org, "logo", "") or "",
        "org_primary_color":   getattr(org, "primary_color", "") or "#B8693C",
        "org_secondary_color": getattr(org, "secondary_color", "") or "#0ea5e9",
    }

    context = org_branding | (md.get("email_context", {}) | {
        "title": n.title, "body": n.body,
        "recipient_email": n.recipient.email,
        "recipient_name": n.recipient.get_full_name() or n.recipient.email,
        "link_url": _absolute(n.action_url or n.link_url),
        "site_name": site_name,
    })
    html, text = render_email(template_base, context)

    # ─── Subject : préfixe org (multi-org) + personnalisation prénom.
    # Format final : "[Datarium] Marie, votre tâche est en retard"
    # Aide les users multi-orgs à identifier rapidement la source de la notif
    # ET aide à passer les filtres anti-spam (personnalisation = transactionnel).
    first_name = (n.recipient.first_name or "").strip()
    if first_name and first_name.lower() not in n.title.lower():
        personalized = (
            f"{first_name}, {n.title[0].lower()}{n.title[1:]}"
            if len(n.title) > 1 else n.title
        )
    else:
        personalized = n.title

    org_name = org_branding["org_name"]
    # Évite la duplication si le titre contient déjà le nom org
    if org_name and f"[{org_name}]" not in personalized and org_name.lower() not in personalized.lower():
        subject = f"[{org_name}] {personalized}"
    else:
        subject = personalized

    # Body fallback : on évite un texte trop court (signal spam). Si pas de
    # template texte rendu, on construit un fallback lisible.
    body_text = text or _build_text_fallback(n, context)

    # ─── From / Reply-To
    # `from_email` peut être au format "Nom <addr@domaine>" — Django gère.
    # `reply_to` doit pointer vers une vraie boîte humaine pour les réponses.
    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or f"{site_name} <noreply@codir.local>"
    )
    reply_to = (
        getattr(settings, "EMAIL_REPLY_TO", None)
        or getattr(settings, "SERVER_EMAIL", None)
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=[n.recipient.email],
        reply_to=[reply_to] if reply_to else None,
    )
    if html:
        msg.attach_alternative(html, "text/html")

    # ── Headers anti-spam (Gmail / Outlook / Apple Mail) ──
    # Stratégie transactionnelle :
    #   * Message-ID stable → threading correct
    #   * List-Unsubscribe + List-Unsubscribe-Post (RFC 8058) → Gmail valorise
    #   * X-Entity-Ref-ID → tracking debug interne
    #   * Date header géré par Django (UTC)
    # On NE met PAS :
    #   * Precedence: bulk (sauf digests) → sinon Gmail flag "promotion"
    #   * Auto-Submitted: auto-generated → bruit pour notifs transactionnelles
    site_url = getattr(settings, "FRONTEND_BASE_URL", "https://codir.datarium-dev.com")
    unsubscribe_url = f"{site_url.rstrip('/')}/notifications/preferences"
    # Domaine extrait de l'adresse (gérant aussi le format "Nom <addr@domaine>")
    raw_from = from_email.split("<")[-1].rstrip(">")
    domain = raw_from.rsplit("@", 1)[-1] if "@" in raw_from else "codir.local"

    headers = {
        "Message-ID": f"<codir-{n.id}@{domain}>",
        "List-Unsubscribe": f"<{unsubscribe_url}>, <mailto:{reply_to or raw_from}?subject=Unsubscribe>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        "X-Entity-Ref-ID": str(n.id),
    }
    # Digest only : marqueur bulk
    if n.event in _DIGEST_EVENTS:
        headers["Precedence"] = "bulk"
        headers["X-Auto-Response-Suppress"] = "OOF, AutoReply"

    msg.extra_headers = headers

    try:
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        err_str = str(exc)[:1000]
        n.failed_at = timezone.now()
        n.error_message = err_str
        n.status = NotificationStatus.FAILED
        n.save(update_fields=["failed_at", "error_message", "status", "updated_at"])
        log_transport(
            notification=n, provider="smtp",
            channel=NotificationChannel.EMAIL,
            status_code="error", error=err_str,
        )
        # Erreur 5xx (permanente) → pas la peine de retry
        if _is_permanent_smtp_error(exc):
            return "failed-permanent"
        raise self.retry(exc=exc)

    mark_email_sent(n)
    log_transport(
        notification=n, provider="smtp",
        channel=NotificationChannel.EMAIL,
        status_code="sent",
    )
    return "sent"


def _is_permanent_smtp_error(exc: Exception) -> bool:
    """Détecte un échec SMTP 5xx (auth, recipient refusé, etc.) où retry est vain."""
    msg = str(exc).lower()
    if any(s in msg for s in (
        "authentication", "auth", "501", "550", "553", "554",
        "relay denied", "recipient", "sender refused",
    )):
        return True
    return False


def _build_text_fallback(notification, context: dict) -> str:
    """Construit un texte plain raisonnable si pas de template texte."""
    lines = [
        f"Bonjour {context.get('recipient_name', '')},",
        "",
        notification.body or notification.title,
        "",
    ]
    link = context.get("link_url") or ""
    if link:
        lines.append(f"Accéder à CODIR : {link}")
        lines.append("")
    lines.append("--")
    lines.append(f"{context.get('site_name', 'CODIR')} — comité exécutif")
    lines.append("Vous pouvez gérer vos préférences de notification "
                 "depuis votre profil dans l'application.")
    return "\n".join(lines)


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
def send_weekly_user_task_digest_task():
    """Synthèse hebdomadaire des tâches NON-TERMINÉES (vendredi 9h00 Africa/Abidjan).

    Pour chaque user actif ayant ≥ 1 tâche ouverte (TODO / IN_PROGRESS /
    BLOCKED / OVERDUE), envoie un email récapitulatif groupé par échéance
    (en retard, cette semaine, plus tard, sans date).

    Anti-doublon : 1 envoi max par user par semaine (clé = lundi de la semaine).
    Si la tâche tourne 2× le même vendredi (retry, redémarrage), seul le 1er envoi
    aboutit — les suivants sont silencieusement ignorés (cf. `prevent_duplicate_reminder`).
    """
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
        try:
            result = send_user_weekly_digest(
                user=user, organization=m.organization, tasks=tasks,
            )
            if result:
                count += 1
        except Exception:  # noqa: BLE001
            logger.exception("Échec digest hebdo pour %s", user.email)
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

@shared_task(name="apps.notifications.tasks.send_notification_push")
def send_notification_push(notification_id: str):
    """Lot 6 — envoi push à toutes les subscriptions actives du recipient.

    Best-effort : non bloquant pour le pipeline notify(). Si VAPID non
    configurées ou pywebpush absent, retourne silencieusement.
    """
    from .push_service import send_push
    n = Notification.unscoped.filter(id=notification_id).select_related(
        "recipient", "organization",
    ).first()
    if not n:
        return
    try:
        return send_push(notification=n)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("send_push KO: %s", exc)


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
