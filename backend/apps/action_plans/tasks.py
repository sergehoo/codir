"""Tâches Celery — action_plans (legacy wrappers).

Conserves les anciens noms pour rétro-compatibilité ; délègue désormais
aux tâches centralisées dans apps.notifications.tasks.
"""
from celery import shared_task


@shared_task
def detect_overdue_tasks():
    from apps.notifications.tasks import detect_overdue_tasks_task
    return detect_overdue_tasks_task.run()


@shared_task
def send_deadline_reminders():
    from apps.notifications.tasks import send_due_soon_alerts_task
    return send_due_soon_alerts_task.run()
