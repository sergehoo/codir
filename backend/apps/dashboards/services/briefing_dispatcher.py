"""Envoi automatique du briefing matinal — Lot Briefing-Auto.

Stratégie :
  - Tâche Celery beat tourne toutes les heures
  - Pour chaque user actif × org : check si l'heure locale courante match
    `daily_briefing_hour` ET `daily_briefing_enabled` ET pas déjà envoyé aujourd'hui
  - Génère le briefing via `generate_daily_briefing`
  - Crée une Notification (event=daily_briefing) qui déclenche email + push
  - Idempotent : trace l'envoi du jour dans `last_briefing_sent_at`
    (stocké via metadata sur Notification pour ne pas migrer encore)

Coût : pour 100 users → 100 briefings/jour générés + 100 emails + 100 push.
Aucun appel LLM si BRIEFING_TAGLINE_LLM_ENABLED=False, sinon 1 par briefing.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def already_sent_today(user, organization) -> bool:
    """Check si on a déjà envoyé un briefing à ce user aujourd'hui."""
    from apps.notifications.models import Notification
    today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return Notification.unscoped.filter(
        organization=organization,
        recipient=user,
        event="daily_briefing",
        created_at__gte=today_start,
    ).exists()


def send_briefing_for_user(*, user, organization) -> bool:
    """Génère le briefing du user et l'envoie via le pipeline notify().

    Returns True si envoi tenté, False si skip (déjà envoyé ou pas opportun).
    """
    from apps.dashboards.services.briefing import generate_daily_briefing
    from apps.notifications.models import (
        NotificationChannel, NotificationEvent, NotificationLevel,
        NotificationPreference,
    )
    from apps.notifications.services import notify

    # Anti-spam
    if already_sent_today(user, organization):
        return False

    # Check pref (default-on)
    pref = NotificationPreference.unscoped.filter(user=user).first()
    if pref and not pref.daily_briefing_enabled:
        return False

    # Génère
    try:
        briefing = generate_daily_briefing(user=user, organization=organization)
    except Exception:  # noqa: BLE001
        logger.exception("Briefing generation KO user=%s", user.id)
        return False

    summary = (briefing.get("summary") or "Votre briefing du jour est prêt.").strip()
    tagline = (briefing.get("tagline") or "").strip()
    markdown = briefing.get("markdown") or ""

    # Notification → déclenche email + push automatiquement via notify pipeline
    try:
        notify(
            organization=organization,
            recipient=user,
            event="daily_briefing",
            level=NotificationLevel.INFO,
            title="Votre briefing du jour",
            body=summary,
            channel=NotificationChannel.EMAIL,  # email + push (toujours déclenchés)
            action_url="/briefing",
            email_template="daily_briefing",
            email_context={
                "summary": summary,
                "tagline": tagline,
                "markdown_html": _markdown_to_html(markdown),
                "stats": briefing.get("stats", {}),
            },
            metadata={
                "briefing_generated_at": briefing.get("generated_at", ""),
            },
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Briefing notify KO user=%s", user.id)
        return False


def dispatch_for_all_users(*, force_hour: int | None = None) -> dict:
    """Itère sur toutes les org actives × users actifs, envoie si l'heure match.

    Args:
        force_hour: si fourni (0-23), ignore la pref `daily_briefing_hour` et
                    envoie à tout user actif. Utile pour les tests/debug.

    Returns: résumé d'envoi.
    """
    from apps.accounts.models import Membership
    from apps.notifications.models import NotificationPreference
    from apps.organizations.models import Organization

    summary = {"checked": 0, "sent": 0, "skipped_pref": 0,
               "skipped_already_sent": 0, "skipped_hour": 0, "errors": 0}

    now_local = timezone.localtime()
    current_hour = force_hour if force_hour is not None else now_local.hour

    for org in Organization.objects.filter(is_active=True):
        memberships = (
            Membership.unscoped
            .filter(organization=org, is_active=True)
            .select_related("user")
        )
        for m in memberships:
            user = m.user
            if not user.is_active or not user.email:
                continue
            summary["checked"] += 1

            # Check pref hour (en force_hour, on saute le check)
            if force_hour is None:
                pref = NotificationPreference.unscoped.filter(user=user).first()
                pref_hour = pref.daily_briefing_hour if pref else 7
                if pref_hour != current_hour:
                    summary["skipped_hour"] += 1
                    continue
                if pref and not pref.daily_briefing_enabled:
                    summary["skipped_pref"] += 1
                    continue

            if already_sent_today(user, org):
                summary["skipped_already_sent"] += 1
                continue

            try:
                if send_briefing_for_user(user=user, organization=org):
                    summary["sent"] += 1
            except Exception:  # noqa: BLE001
                logger.exception("send_briefing_for_user crash u=%s o=%s", user.id, org.id)
                summary["errors"] += 1

    logger.info("dispatch_daily_briefings summary=%s hour=%s", summary, current_hour)
    return summary


def _markdown_to_html(md: str) -> str:
    """Mini renderer markdown → HTML pour emails. Pas de dépendance."""
    if not md:
        return ""
    try:
        import markdown as md_lib
        return md_lib.markdown(md, extensions=["extra", "sane_lists"], output_format="html5")
    except ImportError:
        # Fallback minimal pour ne pas planter
        return f"<pre>{md.replace('<', '&lt;')}</pre>"
