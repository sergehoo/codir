"""Signaux action_plans : audit + notification assignation tâche.

La logique métier reste dans `services.py`. Ces signaux servent au
déclenchement passif (création via DRF/admin/seed) — ils délèguent
à send_task_assigned_notification pour passer par les préférences.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit_logs.services import log as audit_log

from .models import ActionPlan, ActionTask


@receiver(post_save, sender=ActionPlan)
def on_action_plan_saved(sender, instance: ActionPlan, created, **kwargs):
    if created:
        audit_log(action="created", target=instance, description=f"Plan d'action : {instance.title}")


@receiver(post_save, sender=ActionTask)
def on_action_task_saved(sender, instance: ActionTask, created, **kwargs):
    if created:
        audit_log(action="created", target=instance, description=f"Tâche : {instance.title}")
        if instance.assignee:
            try:
                from apps.notifications.services import send_task_assigned_notification
                send_task_assigned_notification(task=instance)
            except Exception:  # noqa: BLE001
                pass
