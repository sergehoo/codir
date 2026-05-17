"""Tâches Celery — meetings (rappels + génération des séries récurrentes)."""
import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from apps.common.enums import MeetingStatus
from apps.notifications.models import NotificationEvent, NotificationLevel
from apps.notifications.services import notify

from .models import Meeting, MeetingFrequency, MeetingSeries

log = logging.getLogger(__name__)


@shared_task
def send_meeting_reminders():
    """Rappel J-1 / H-1 aux participants des réunions à venir."""
    now = timezone.now()
    windows = [
        (now + timedelta(hours=24), timedelta(minutes=15)),
        (now + timedelta(hours=1), timedelta(minutes=15)),
    ]
    notified = 0
    for target_time, window in windows:
        qs = Meeting.unscoped.filter(
            status=MeetingStatus.SCHEDULED,
            scheduled_start__gte=target_time - window,
            scheduled_start__lt=target_time + window,
        ).select_related("organization")
        for m in qs:
            for p in m.participants.select_related("user"):
                if not p.user:
                    continue
                notify(
                    organization=m.organization, recipient=p.user,
                    event=NotificationEvent.MEETING_REMINDER,
                    level=NotificationLevel.INFO,
                    title=f"Rappel : {m.title}",
                    body=f"Début : {m.scheduled_start:%d/%m %H:%M}",
                    target=m, link_url=f"/meetings/{m.id}",
                    send_email=True,
                )
                notified += 1
    return notified


# ─── Génération automatique des instances depuis MeetingSeries ──────────

def _occurrence_dates(series: MeetingSeries, since, until) -> list:
    """Retourne la liste des dates d'occurrences d'une série entre [since, until]."""
    dates: list = []
    cursor = since

    if series.frequency == MeetingFrequency.MONTHLY:
        # Une fois par mois au jour `day_of_month`
        day = series.day_of_month or 1
        while cursor <= until:
            try:
                target = cursor.replace(day=day)
            except ValueError:
                # Mois plus court que `day` (ex: 31 février) → on saute
                cursor = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
                continue
            if target >= since and target <= until:
                dates.append(target)
            # Mois suivant
            next_month = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
            cursor = next_month
        return dates

    # Weekly / Biweekly : on cherche la prochaine occurrence du day_of_week
    step_days = 7 if series.frequency == MeetingFrequency.WEEKLY else 14
    # Aller au prochain `day_of_week` depuis since
    delta = (series.day_of_week - cursor.weekday()) % 7
    cursor = cursor + timedelta(days=delta)
    while cursor <= until:
        dates.append(cursor)
        cursor = cursor + timedelta(days=step_days)
    return dates


@shared_task
def generate_recurring_meetings():
    """Génère les instances Meeting à venir pour chaque MeetingSeries active.

    Programmé via Celery beat (quotidien à 02h00). Idempotent : utilise
    ``get_or_create`` sur (series, scheduled_start).
    """
    today = timezone.localdate()
    total_series = total_created = 0

    for series in MeetingSeries.unscoped.filter(is_active=True).select_related(
        "organization", "default_chair", "default_secretary",
    ).prefetch_related("default_participants"):
        try:
            target_end = today + timedelta(weeks=series.generate_weeks_ahead)
            if series.ends_on and series.ends_on < target_end:
                target_end = series.ends_on

            start_from = series.last_generated_until or series.starts_on or today
            if start_from < today:
                start_from = today  # ne jamais générer dans le passé

            if start_from > target_end:
                continue

            occurrences = _occurrence_dates(series, start_from, target_end)
            local_tz = timezone.get_current_timezone()
            created_for_series = 0

            for occ_date in occurrences:
                start_dt = timezone.make_aware(
                    datetime.combine(occ_date, series.time), local_tz,
                )
                end_dt = start_dt + timedelta(minutes=series.duration_minutes)

                meeting, created = Meeting.unscoped.get_or_create(
                    series=series,
                    scheduled_start=start_dt,
                    defaults={
                        "organization": series.organization,
                        "title": f"{series.title} — {occ_date:%d/%m/%Y}",
                        "description": series.description,
                        "meeting_type": series.meeting_type,
                        "scheduled_end": end_dt,
                        "status": MeetingStatus.SCHEDULED,
                        "location": series.location,
                        "video_url": series.video_url,
                        "chair": series.default_chair,
                        "secretary": series.default_secretary,
                    },
                )
                if created:
                    created_for_series += 1
                    # Copier les participants par défaut
                    from .models import MeetingParticipant
                    from apps.common.enums import ParticipantRole
                    for user in series.default_participants.all():
                        role = ParticipantRole.MEMBER
                        if series.default_chair_id == user.id:
                            role = ParticipantRole.CHAIR
                        elif series.default_secretary_id == user.id:
                            role = ParticipantRole.SECRETARY
                        MeetingParticipant.unscoped.get_or_create(
                            organization=series.organization,
                            meeting=meeting,
                            user=user,
                            defaults={
                                "role": role,
                                "is_required": True,
                                "external_email": None,
                            },
                        )

            series.last_generated_until = target_end
            series.save(update_fields=["last_generated_until"])
            total_series += 1
            total_created += created_for_series

        except Exception:  # noqa: BLE001
            log.exception("Failed generating meetings for series %s", series.id)
            continue

    # Phase post-création : envoi des invitations email aux participants
    # uniquement pour les meetings créés à l'instant (last 10 min)
    try:
        from .invitations import send_invitations_for_meeting
        cutoff = timezone.now() - timedelta(minutes=10)
        new_meetings = Meeting.unscoped.filter(
            series__isnull=False,
            created_at__gte=cutoff,
            status=MeetingStatus.SCHEDULED,
        ).select_related("organization")
        for m in new_meetings:
            try:
                send_invitations_for_meeting(m)
            except Exception:  # noqa: BLE001
                log.exception("Invitation send failed for meeting %s", m.id)
    except Exception:  # noqa: BLE001
        log.exception("Bulk invitation phase failed")

    log.info(
        "generate_recurring_meetings: %s séries traitées, %s instances créées",
        total_series, total_created,
    )
    return {"series": total_series, "meetings_created": total_created}
