"""Signaux action_plans : audit + notification assignation tâche.

La logique métier reste dans `services.py`. Ces signaux servent au
déclenchement passif (création via DRF/admin/seed) — ils délèguent
à send_task_assigned_notification pour passer par les préférences.
"""
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from apps.audit_logs.services import log as audit_log

from .models import ActionPlan, ActionTask


@receiver(post_save, sender=ActionPlan)
def on_action_plan_saved(sender, instance: ActionPlan, created, **kwargs):
    if created:
        audit_log(action="created", target=instance, description=f"Plan d'action : {instance.title}")


def _safe_notify_assigned(task_id):
    """Récupère la tâche fraîche pour avoir les co_assignees mis à jour
    (post commit du M2M.set()) et envoie la notif lead + co-responsables.
    """
    try:
        from apps.notifications.services import send_task_assigned_notification
        # Refresh : on lit la tâche depuis la DB pour avoir le M2M attaché
        task = ActionTask.unscoped.filter(id=task_id).first()
        if task:
            send_task_assigned_notification(task=task)
    except Exception:  # noqa: BLE001
        pass


@receiver(post_save, sender=ActionTask)
def on_action_task_saved(sender, instance: ActionTask, created, **kwargs):
    if created:
        audit_log(action="created", target=instance, description=f"Tâche : {instance.title}")
        # On défère la notif au commit de la transaction pour deux raisons :
        # 1. Les M2M (co_assignees) sont set() APRÈS la création de la tâche
        #    par `services.create_task` — donc inaccessibles depuis post_save.
        # 2. Si la transaction rollback (erreur métier en aval), on évite
        #    d'envoyer un email qui pointerait sur une tâche fantôme.
        task_id = instance.id
        transaction.on_commit(lambda: _safe_notify_assigned(task_id))


@receiver(m2m_changed, sender=ActionTask.co_assignees.through)
def on_co_assignees_changed(sender, instance, action, pk_set, **kwargs):
    """Notifie les co-responsables NOUVELLEMENT ajoutés via PATCH/edit.

    Couvre le cas : on modifie une tâche existante pour y ajouter des
    co_assignees. Le post_save aura déjà été passé (created=False) sans
    notifier. Ce handler comble ce trou.

    Dédup : si une notif TASK_ASSIGNED existe déjà pour ce (user, task),
    on ne ré-envoie pas (évite le doublon avec le flux de création où le
    post_save + on_commit a déjà notifié les co_assignees initiaux).
    """
    if action != "post_add" or not pk_set:
        return
    if not isinstance(instance, ActionTask):
        return  # le reverse signal (User → tasks_co_assigned) — pas notre cas

    task_id = instance.id
    new_user_ids = set(pk_set)

    def _notify_new_co_assignees():
        try:
            from apps.accounts.models import User
            from apps.notifications.models import Notification, NotificationEvent
            from apps.notifications.services import notify, _priority_from_task, _user_label, _task_context

            task = ActionTask.unscoped.filter(id=task_id).first()
            if not task:
                return
            users = list(User.objects.filter(id__in=new_user_ids))
            if not users:
                return

            ct = ContentType.objects.get_for_model(ActionTask)
            already_notified_ids = set(
                Notification.unscoped.filter(
                    event=NotificationEvent.TASK_ASSIGNED,
                    recipient_id__in=new_user_ids,
                    target_type=ct,
                    target_id=str(task.id),
                ).values_list("recipient_id", flat=True),
            )

            lead_label = _user_label(task.assignee) if task.assignee else "—"
            due_str = task.due_date.isoformat() if task.due_date else "—"
            base_ctx = _task_context(task) | {
                "is_co_assignee": True,
                "lead_name": lead_label,
            }

            for user in users:
                if user.id in already_notified_ids:
                    continue
                if user.id == task.assignee_id:
                    continue
                notify(
                    organization=task.organization,
                    recipient=user,
                    event=NotificationEvent.TASK_ASSIGNED,
                    channel="email",
                    title=f"Vous êtes co-responsable : {task.title}",
                    body=(f"Vous avez été ajouté(e) comme **co-responsable** "
                          f"de la tâche **{task.title}**.\n"
                          f"Responsable principal : {lead_label}\n"
                          f"Échéance : {due_str}"),
                    target=task,
                    link_url=f"/action-plans/{task.action_plan_id}",
                    action_url=f"/action-plans/{task.action_plan_id}",
                    send_email=True,
                    email_template="task_assigned",
                    email_context=base_ctx,
                    priority=_priority_from_task(task),
                )
        except Exception:  # noqa: BLE001
            pass

    transaction.on_commit(_notify_new_co_assignees)
