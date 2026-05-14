"""Tests cycle de vie décision + plan d'action."""
import pytest
from datetime import date, timedelta

from apps.common.enums import DecisionStatus
from apps.common.exceptions import TransitionNotAllowed
from apps.decisions import services
from apps.decisions.models import Decision


@pytest.fixture
def decision(db, org, user):
    return services.create_decision(
        organization=org, created_by=user,
        data={
            "title": "Lancer Phoenix",
            "description_md": "Investissement 4,2 M€",
            "priority": "critical",
            "impact": "strategic",
            "responsible": user,
            "deadline": date.today() + timedelta(days=180),
        },
    )


@pytest.mark.django_db
def test_create_decision_auto_assigns_ref(decision):
    assert decision.ref.startswith("DEC-")
    assert len(decision.ref) >= 12


@pytest.mark.django_db
def test_decision_history_records_creation(decision):
    assert decision.history.filter(event="created").exists()


@pytest.mark.django_db
def test_cannot_start_unapproved_decision(decision, user):
    with pytest.raises(TransitionNotAllowed):
        services.start_decision(decision=decision, actor=user)


@pytest.mark.django_db
def test_approve_then_convert_to_action_plan(decision, user):
    services.approve_decision(decision=decision, approver=user)
    decision.refresh_from_db()
    assert decision.status == DecisionStatus.APPROVED

    plan = services.convert_to_action_plan(
        decision=decision, actor=user,
        tasks=[{"title": "Sub 1", "priority": "high"}],
    )
    assert plan.tasks.count() == 1
    assert plan.decision_id == decision.id
    # 2e appel doit retourner le même plan (idempotence)
    assert services.convert_to_action_plan(decision=decision, actor=user).id == plan.id


@pytest.mark.django_db
def test_cannot_convert_unapproved_decision(decision, user):
    with pytest.raises(TransitionNotAllowed):
        services.convert_to_action_plan(decision=decision, actor=user)
