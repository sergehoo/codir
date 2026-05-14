"""Signaux meetings : audit auto + notification invitation."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit_logs.services import log as audit_log
from apps.notifications.models import NotificationEvent
from apps.notifications.services import notify

from .models import Meeting, MeetingParticipant


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
    notify(
        organization=instance.organization,
        recipient=instance.user,
        event=NotificationEvent.MEETING_INVITED,
        title=f"Invitation : {instance.meeting.title}",
        body=f"Début prévu : {instance.meeting.scheduled_start:%d/%m/%Y %H:%M}",
        target=instance.meeting,
        link_url=f"/meetings/{instance.meeting_id}",
        send_email=True,
    )
