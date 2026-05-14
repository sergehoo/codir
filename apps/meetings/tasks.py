"""Tâches Celery — meetings (rappels)."""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.common.enums import MeetingStatus
from apps.notifications.models import NotificationEvent, NotificationLevel
from apps.notifications.services import notify

from .models import Meeting


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
