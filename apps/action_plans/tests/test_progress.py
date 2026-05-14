"""Tests progress + overdue."""
import pytest
from datetime import timedelta

from django.utils import timezone

from apps.action_plans import services
from apps.action_plans.models import ActionPlan, ActionTask
from apps.action_plans.tasks import detect_overdue_tasks
from apps.common.enums import ActionPlanStatus, ActionTaskStatus
from apps.decisions.models import Decision


@pytest.fixture
def plan(db, org, user):
    d = Decision.unscoped.create(
        organization=org, ref="DEC-2026-0001", title="x",
        status="approved", created_by=user, responsible=user,
    )
    return ActionPlan.unscoped.create(organization=org, decision=d, title="P", owner=user)


@pytest.mark.django_db
def test_update_progress_changes_status(plan, user):
    t = services.create_task(action_plan=plan, data={"title": "T1", "priority": "medium"})
    services.update_progress(task=t, progress_percent=40, actor=user)
    t.refresh_from_db()
    assert t.progress_percent == 40
    assert t.status == ActionTaskStatus.IN_PROGRESS


@pytest.mark.django_db
def test_completing_all_tasks_marks_plan_completed(plan, user):
    t = services.create_task(action_plan=plan, data={"title": "T1", "priority": "medium"})
    services.complete_task(task=t, actor=user)
    plan.refresh_from_db()
    assert plan.status == ActionPlanStatus.COMPLETED
    assert plan.progress_percent == 100


@pytest.mark.django_db
def test_overdue_detection_marks_status(plan, user):
    yesterday = (timezone.now() - timedelta(days=1)).date()
    t = ActionTask.unscoped.create(
        organization=plan.organization, action_plan=plan, title="Late",
        priority="high", status=ActionTaskStatus.TODO, due_date=yesterday, assignee=user,
    )
    detect_overdue_tasks()
    t.refresh_from_db()
    assert t.status == ActionTaskStatus.OVERDUE
