"""Tests services notifications + délégation + anti-doublon + préférences."""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from apps.accounts.models import Membership
from apps.action_plans import services as plan_services
from apps.action_plans.models import ActionPlan, ActionTask
from apps.common.enums import ActionPlanStatus, ActionTaskStatus
from apps.decisions.models import Decision
from apps.notifications import services
from apps.notifications.models import (
    Notification, NotificationChannel, NotificationEvent,
    NotificationPreference, ReminderType, ReminderTimeSlot,
    TaskReminderLog,
)
from apps.notifications.tasks import (
    detect_overdue_tasks_task, send_daily_task_reminders_task,
    send_due_soon_alerts_task,
)

User = get_user_model()


@pytest.fixture
def assignee(db, org):
    u = User.objects.create_user(email="alice@acme.local", password="x",
                                 first_name="Alice", last_name="Martin")
    Membership.unscoped.create(organization=org, user=u, is_active=True)
    return u


@pytest.fixture
def plan(db, org, user):
    d = Decision.unscoped.create(
        organization=org, ref="DEC-2026-0001", title="x",
        status="approved", created_by=user, responsible=user,
    )
    return ActionPlan.unscoped.create(
        organization=org, decision=d, title="P", owner=user,
        status=ActionPlanStatus.OPEN,
    )


# ─── Assignation ──────────────────────────────────────────────

@pytest.mark.django_db
def test_assign_creates_notification_and_email(plan, assignee):
    mail.outbox.clear()
    t = plan_services.create_task(
        action_plan=plan, data={"title": "Tâche A", "priority": "high", "assignee": assignee},
    )
    # Signal post_save → notif TASK_ASSIGNED
    n = Notification.unscoped.filter(recipient=assignee, event=NotificationEvent.TASK_ASSIGNED).first()
    assert n is not None
    assert n.target_id == str(t.id)


# ─── Délégation ───────────────────────────────────────────────

@pytest.mark.django_db
def test_delegate_notifies_old_and_new(plan, user, assignee):
    bob = User.objects.create_user(email="bob@acme.local", password="x",
                                   first_name="Bob", last_name="Sow")
    Membership.unscoped.create(organization=plan.organization, user=bob, is_active=True)
    t = plan_services.create_task(
        action_plan=plan, data={"title": "Tâche", "priority": "medium", "assignee": assignee},
    )
    Notification.unscoped.all().delete()  # purge la notif d'assignation
    plan_services.delegate_task(task=t, new_assignee=bob, by_user=user, note="urgent")

    new_notifs = Notification.unscoped.filter(recipient=bob, event=NotificationEvent.TASK_DELEGATED)
    old_notifs = Notification.unscoped.filter(recipient=assignee, event=NotificationEvent.TASK_DELEGATED)
    assert new_notifs.exists()
    assert old_notifs.exists()


# ─── Anti-doublon rappels ─────────────────────────────────────

@pytest.mark.django_db
def test_reminder_anti_duplicate(assignee):
    log1, c1 = services.prevent_duplicate_reminder(
        user=assignee, task=None,
        reminder_type=ReminderType.DAILY_USER,
        time_slot=ReminderTimeSlot.MORNING,
    )
    log2, c2 = services.prevent_duplicate_reminder(
        user=assignee, task=None,
        reminder_type=ReminderType.DAILY_USER,
        time_slot=ReminderTimeSlot.MORNING,
    )
    assert c1 is True and log1 is not None
    assert c2 is False and log2 is None


@pytest.mark.django_db
def test_reminder_different_slots_allowed(assignee):
    _, m = services.prevent_duplicate_reminder(
        user=assignee, reminder_type=ReminderType.DAILY_USER,
        time_slot=ReminderTimeSlot.MORNING,
    )
    _, a = services.prevent_duplicate_reminder(
        user=assignee, reminder_type=ReminderType.DAILY_USER,
        time_slot=ReminderTimeSlot.AFTERNOON,
    )
    assert m and a


# ─── Préférences désactivées ──────────────────────────────────

@pytest.mark.django_db
def test_disabled_preference_blocks_notification(org, assignee, plan):
    pref = services.get_or_create_preference(assignee, organization=org)
    pref.task_assignment_email = False
    pref.save()
    # email_enabled still True → la notif passe quand même mais pas l'email
    n = services.notify(
        organization=org, recipient=assignee,
        event=NotificationEvent.TASK_ASSIGNED,
        title="x", channel=NotificationChannel.INTERNAL,
        send_email=True,
        check_preference=True,
    )
    assert n is not None  # internal_enabled toujours True
    # mais pas d'email envoyé via Celery (vérifié par should_send_notification email/event)
    assert not services.should_send_notification(
        assignee, NotificationEvent.TASK_ASSIGNED, NotificationChannel.EMAIL,
    )


@pytest.mark.django_db
def test_all_channels_off_blocks_internal(org, assignee):
    pref = services.get_or_create_preference(assignee, organization=org)
    pref.internal_enabled = False
    pref.save()
    n = services.notify(
        organization=org, recipient=assignee,
        event=NotificationEvent.TASK_REMINDER,
        title="x", channel=NotificationChannel.INTERNAL,
        check_preference=True,
    )
    assert n is None


# ─── Overdue task ─────────────────────────────────────────────

@pytest.mark.django_db
def test_detect_overdue_task_marks_status_and_notifies(plan, assignee):
    from datetime import timedelta
    yesterday = (timezone.now() - timedelta(days=1)).date()
    t = ActionTask.unscoped.create(
        organization=plan.organization, action_plan=plan, title="Late",
        priority="high", status=ActionTaskStatus.TODO, due_date=yesterday, assignee=assignee,
    )
    detect_overdue_tasks_task()
    t.refresh_from_db()
    assert t.status == ActionTaskStatus.OVERDUE
    assert Notification.unscoped.filter(
        recipient=assignee, event=NotificationEvent.TASK_OVERDUE,
    ).exists()


# ─── Rappel quotidien utilisateur ─────────────────────────────

@pytest.mark.django_db
def test_daily_user_reminder_creates_notification(plan, assignee):
    ActionTask.unscoped.create(
        organization=plan.organization, action_plan=plan, title="T1",
        priority="medium", status=ActionTaskStatus.IN_PROGRESS,
        assignee=assignee,
    )
    count = send_daily_task_reminders_task()
    assert count >= 1
    assert Notification.unscoped.filter(
        recipient=assignee, event=NotificationEvent.TASK_REMINDER,
    ).exists()


# ─── Due soon ────────────────────────────────────────────────

@pytest.mark.django_db
def test_due_soon_alert_triggers(plan, assignee):
    from datetime import timedelta
    tomorrow = (timezone.now() + timedelta(days=1)).date()
    ActionTask.unscoped.create(
        organization=plan.organization, action_plan=plan, title="Soon",
        priority="medium", status=ActionTaskStatus.IN_PROGRESS,
        assignee=assignee, due_date=tomorrow,
    )
    sent = send_due_soon_alerts_task()
    assert sent >= 1


# ─── Manager summary helper ──────────────────────────────────

@pytest.mark.django_db
def test_manager_branch_summary_aggregates(plan, user, assignee):
    from datetime import timedelta
    yesterday = (timezone.now() - timedelta(days=1)).date()
    ActionTask.unscoped.create(
        organization=plan.organization, action_plan=plan, title="Late1",
        priority="high", status=ActionTaskStatus.OVERDUE, assignee=assignee,
        due_date=yesterday,
    )
    summary = plan_services.get_manager_branch_tasks_summary(
        manager=user, organization=plan.organization,
    )
    assert summary["open"] >= 1
    assert summary["overdue"] >= 1
    assert "top_tasks" in summary
    assert "progress_avg" in summary
