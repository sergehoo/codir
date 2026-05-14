"""Tests workflow meetings — bêta."""
import pytest
from datetime import timedelta

from django.utils import timezone

from apps.agendas.models import Agenda, AgendaItem
from apps.agendas.services import validate_agenda
from apps.common.enums import (
    AgendaItemStatus, AttendanceStatus, MeetingStatus, ParticipantRole,
)
from apps.meetings import services as meeting_services
from apps.meetings.models import Meeting, MeetingAttendance, MeetingParticipant


@pytest.fixture
def meeting(db, org, user):
    now = timezone.now()
    return meeting_services.create_meeting(
        organization=org, created_by=user,
        data={
            "title": "Test CODIR", "meeting_type": "regular",
            "scheduled_start": now + timedelta(days=1),
            "scheduled_end": now + timedelta(days=1, hours=2),
            "chair": user, "secretary": user, "quorum_min": 1,
        },
    )


@pytest.mark.django_db
def test_create_meeting_auto_adds_chair_and_secretary(meeting):
    parts = MeetingParticipant.unscoped.filter(meeting=meeting)
    roles = {p.role for p in parts}
    assert ParticipantRole.CHAIR in roles
    assert ParticipantRole.SECRETARY in roles


@pytest.mark.django_db
def test_start_meeting_requires_validated_agenda(meeting, user):
    Agenda.unscoped.create(organization=meeting.organization, meeting=meeting)
    meeting.status = MeetingStatus.SCHEDULED
    meeting.save()
    with pytest.raises(Exception):
        meeting_services.start_meeting(meeting, by_user=user)


@pytest.mark.django_db
def test_complete_meeting_generates_minutes(meeting, user):
    a = Agenda.unscoped.create(organization=meeting.organization, meeting=meeting)
    AgendaItem.unscoped.create(organization=meeting.organization, agenda=a, order=1, title="Sujet 1")
    validate_agenda(agenda=a, validator=user)
    meeting.refresh_from_db()
    meeting_services.start_meeting(meeting, by_user=user)
    meeting.refresh_from_db()
    # 1 participant présent pour atteindre quorum
    part = MeetingParticipant.unscoped.filter(meeting=meeting).first()
    MeetingAttendance.unscoped.create(
        organization=meeting.organization, meeting=meeting,
        participant=part, status=AttendanceStatus.PRESENT,
    )
    meeting_services.complete_meeting(meeting, by_user=user)
    meeting.refresh_from_db()
    assert meeting.status == MeetingStatus.COMPLETED
    assert meeting.minutes_generated_at is not None
    assert meeting.minutes.body_html.startswith("<article")


@pytest.mark.django_db
def test_completed_meeting_cannot_be_modified_by_business_rule(meeting, user):
    a = Agenda.unscoped.create(organization=meeting.organization, meeting=meeting)
    AgendaItem.unscoped.create(organization=meeting.organization, agenda=a, order=1, title="X")
    validate_agenda(agenda=a, validator=user)
    meeting.refresh_from_db()
    meeting_services.start_meeting(meeting, by_user=user)
    meeting.refresh_from_db()
    meeting_services.complete_meeting(meeting, by_user=user)
    meeting.refresh_from_db()
    assert meeting.is_locked
