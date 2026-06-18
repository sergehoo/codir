"""Signaux meetings : audit auto + notification invitation intelligente.

Stratégie d'envoi des invitations :
  - Si la réunion est DÉJÀ PASSÉE → pas d'invitation (évite spam sur
    données legacy / réunions clôturées rétroactivement).
  - Si la réunion est dans plus de MEETING_INVITE_HORIZON_DAYS (défaut 30j)
    → on n'envoie PAS d'invitation immédiate. Le user recevra :
        * une notif "Cette semaine" J-7 (via tâche Celery dédiée — à ajouter)
        * les rappels J-1 et H-1 qui existent déjà
    Justification : éviter de spammer 12 emails d'un coup quand une série
    récurrente est générée d'avance sur 12 mois.
  - Si elle est dans les MEETING_INVITE_HORIZON_DAYS prochains jours →
    invitation envoyée normalement.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.audit_logs.services import log as audit_log
from apps.notifications.models import NotificationEvent
from apps.notifications.services import notify

from .models import Meeting, MeetingParticipant

logger = logging.getLogger(__name__)

# Horizon par défaut : 30 jours. Configurable via settings.
DEFAULT_INVITE_HORIZON_DAYS = 30


def _humanize_delay(target_dt) -> str:
    """Retourne une mention humaine du délai : 'demain', 'dans 3 jours', etc."""
    if target_dt is None:
        return ""
    now = timezone.now()
    if target_dt < now:
        return "(réunion passée)"
    delta = target_dt - now
    days = delta.days
    hours = delta.seconds // 3600
    if days == 0:
        if hours <= 1:
            return f"dans environ {max(1, delta.seconds // 60)} min"
        return f"dans {hours}h"
    if days == 1:
        return "demain"
    if days < 7:
        return f"dans {days} jours"
    if days < 14:
        return "la semaine prochaine"
    if days < 30:
        return f"dans {days // 7} semaines"
    return f"dans {days} jours"


@receiver(post_save, sender=Meeting)
def on_meeting_saved(sender, instance: Meeting, created, **kwargs):
    if created:
        audit_log(
            action="created", target=instance, actor=instance.created_by,
            description=f"Réunion créée : {instance.title}",
        )
    else:
        audit_log(
            action="updated", target=instance, actor=None,
            description=f"Réunion mise à jour : {instance.title} (status={instance.status})",
        )


@receiver(post_save, sender=MeetingParticipant)
def on_participant_added(sender, instance: MeetingParticipant, created, **kwargs):
    if not created or instance.user is None:
        return

    meeting = instance.meeting
    start = getattr(meeting, "scheduled_start", None)
    if start is None:
        # Sans date planifiée, on n'envoie pas (cas d'usage rare/brouillon)
        logger.info(
            "Skip invitation meeting=%s : scheduled_start non défini",
            meeting.id,
        )
        return

    now = timezone.now()
    horizon_days = int(
        getattr(settings, "MEETING_INVITE_HORIZON_DAYS", DEFAULT_INVITE_HORIZON_DAYS),
    )
    horizon = now + timedelta(days=horizon_days)

    # Skip réunions passées
    if start < now:
        logger.info(
            "Skip invitation meeting=%s : déjà passée (start=%s)",
            meeting.id, start,
        )
        return

    # Skip réunions trop lointaines (séries récurrentes générées à l'année)
    if start > horizon:
        logger.info(
            "Skip invitation meeting=%s : trop lointaine (start=%s > horizon %sj)",
            meeting.id, start, horizon_days,
        )
        return

    # ─── Envoi : invitation enrichie avec délai humain ─────
    when_human = _humanize_delay(start)
    body_lines = [
        f"📅 Début : {start:%A %d %B %Y à %Hh%M}",
    ]
    if when_human:
        body_lines.append(f"⏱ {when_human.capitalize()}")
    if meeting.location:
        body_lines.append(f"📍 Lieu : {meeting.location}")

    notify(
        organization=instance.organization,
        recipient=instance.user,
        event=NotificationEvent.MEETING_INVITED,
        title=f"Invitation : {meeting.title}",
        body="\n".join(body_lines),
        target=meeting,
        link_url=f"/meetings/{instance.meeting_id}",
        send_email=True,
    )
