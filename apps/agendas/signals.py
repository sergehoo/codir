"""Signaux agendas : audit auto + notif validation."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit_logs.services import log as audit_log
from apps.notifications.models import NotificationEvent, NotificationLevel
from apps.notifications.services import notify

from .models import Agenda


@receiver(post_save, sender=Agenda)
def on_agenda_saved(sender, instance: Agenda, created, **kwargs):
    if created:
        audit_log(action="created", target=instance, description=f"Agenda créé pour {instance.meeting.title}")
        return
    if instance.is_validated and instance.validated_at:
        audit_log(
            action="validated", target=instance, actor=instance.validated_by,
            description=f"Ordre du jour validé : {instance.meeting.title}",
        )
        # Notifier les participants
        for p in instance.meeting.participants.select_related("user"):
            if p.user:
                notify(
                    organization=instance.organization, recipient=p.user,
                    event=NotificationEvent.AGENDA_VALIDATED, level=NotificationLevel.INFO,
                    title=f"Ordre du jour validé : {instance.meeting.title}",
                    target=instance.meeting,
                    link_url=f"/meetings/{instance.meeting_id}",
                )
