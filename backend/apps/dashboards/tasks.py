"""Tâches Celery pour les dashboards — EPI Score quotidien + alertes."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def snapshot_epi_score_daily():
    """Snapshot quotidien de l'EPI Score pour CHAQUE organisation active.

    Programmé via Celery beat à 06h00 chaque jour. Idempotent.
    Si la chute vs J-1 dépasse le seuil, déclenche une alerte aux exécutifs.
    """
    from apps.dashboards.services.epi_score import persist_snapshot, DROP_ALERT_THRESHOLD
    from apps.organizations.models import Organization

    today = timezone.localdate()
    total = created_count = updated_count = alerts = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            snapshot, created, delta = persist_snapshot(org, today)
        except Exception:  # noqa: BLE001
            logger.exception("EPI snapshot failed for org %s", org.slug)
            continue

        total += 1
        if created:
            created_count += 1
        else:
            updated_count += 1

        # Alerte chute > N points
        if delta <= -DROP_ALERT_THRESHOLD and not snapshot.drop_alert_sent:
            try:
                send_epi_drop_alert.delay(str(snapshot.id))
                snapshot.drop_alert_sent = True
                snapshot.save(update_fields=["drop_alert_sent"])
                alerts += 1
            except Exception:  # noqa: BLE001
                logger.exception("EPI drop alert dispatch failed for org %s", org.slug)

    logger.info(
        "EPI daily snapshots: total=%s created=%s updated=%s alerts=%s",
        total, created_count, updated_count, alerts,
    )
    return {
        "total": total,
        "created": created_count,
        "updated": updated_count,
        "alerts": alerts,
    }


@shared_task
def send_epi_drop_alert(snapshot_id: str):
    """Envoie un email aux executive members quand l'EPI chute > seuil."""
    from apps.accounts.models import User
    from apps.dashboards.models import EpiScoreSnapshot
    from apps.notifications.services import create_notification

    snapshot = EpiScoreSnapshot.unscoped.filter(id=snapshot_id).select_related("organization").first()
    if not snapshot:
        return 0

    org = snapshot.organization
    title = f"⚠️ EPI Score en chute : {snapshot.overall_score} ({snapshot.drop_vs_previous:+d} pts)"
    body = (
        f"L'Executive Performance Index de {org.name} a chuté de "
        f"{abs(snapshot.drop_vs_previous)} points en 24h.\n\n"
        f"Composantes ({snapshot.date}):\n"
        f"  • Complétion   : {snapshot.completion_score}/100\n"
        f"  • Ponctualité  : {snapshot.punctuality_score}/100\n"
        f"  • Vélocité     : {snapshot.velocity_score}/100\n"
        f"  • Quorum CODIR : {snapshot.quorum_score}/100\n"
        f"  • Tâches en retard : {snapshot.tasks_overdue} (pénalité -{snapshot.overdue_penalty} pts)\n"
    )

    sent = 0
    qs = User.objects.filter(
        memberships__organization=org,
        memberships__is_executive=True,
        memberships__is_active=True,
        is_active=True,
    ).distinct()

    for user in qs:
        try:
            create_notification(
                organization=org,
                recipient=user,
                title=title,
                body=body,
                event="epi_drop",
                level="warning",
                link_url="/",
            )
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("EPI drop notification failed for %s", user.email)

    logger.info("EPI drop alert sent to %s executives (org=%s)", sent, org.slug)
    return sent


@shared_task(
    name="apps.dashboards.tasks.send_daily_briefings",
    autoretry_for=(Exception,),
    retry_backoff=120,
    retry_kwargs={"max_retries": 1},
)
def send_daily_briefings():
    """Envoie le briefing matinal aux users dont l'heure préférée matche maintenant.

    Configuré dans CELERY_BEAT_SCHEDULE pour tourner toutes les heures pile.
    Idempotent : check "déjà envoyé aujourd'hui" via Notification.
    """
    from apps.dashboards.services.briefing_dispatcher import dispatch_for_all_users
    return dispatch_for_all_users()
