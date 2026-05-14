"""Signaux decisions : audit auto + notifications."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit_logs.services import log as audit_log
from apps.notifications.models import NotificationEvent, NotificationLevel
from apps.notifications.services import notify

from .models import Decision


@receiver(post_save, sender=Decision)
def on_decision_saved(sender, instance: Decision, created, **kwargs):
    if created:
        audit_log(
            action="created", target=instance, actor=instance.created_by,
            description=f"Décision créée : {instance.ref} {instance.title}",
        )
        if instance.responsible:
            notify(
                organization=instance.organization,
                recipient=instance.responsible,
                event=NotificationEvent.DECISION_ASSIGNED,
                title=f"Décision assignée : {instance.ref}",
                body=instance.title,
                target=instance,
                link_url=f"/decisions/{instance.id}",
                send_email=True,
            )
    else:
        audit_log(
            action="updated", target=instance, actor=None,
            description=f"Décision {instance.ref} → {instance.status}",
        )
        if instance.status == "approved" and instance.responsible:
            notify(
                organization=instance.organization,
                recipient=instance.responsible,
                event=NotificationEvent.DECISION_APPROVED,
                level=NotificationLevel.SUCCESS,
                title=f"Décision validée : {instance.ref}",
                body=instance.title,
                target=instance,
                link_url=f"/decisions/{instance.id}",
            )
