"""Permissions DRF — qui peut voir / modifier un enregistrement ?

Règles métier :
- Lecture (list/retrieve/status) : tout participant officiel à la réunion.
- Démarrage / upload : chair, secretary, ou n'importe quel participant
  (la bêta autorise tout participant pour permettre le délégué de prise de
  notes — peut être resserré ensuite via setting).
- Mapping speakers / validation extractions : chair, secretary,
  ou l'auteur (recorded_by).
- Suppression : chair, secretary, ou owner d'org.
"""
from __future__ import annotations

from rest_framework import permissions


def _is_participant(user, meeting) -> bool:
    if user.is_anonymous:
        return False
    try:
        return meeting.participants.filter(user=user).exists()
    except Exception:  # noqa: BLE001
        return False


def _is_chair_or_secretary(user, meeting) -> bool:
    return user.is_authenticated and (
        meeting.chair_id == user.id or meeting.secretary_id == user.id
    )


class CanAccessMeetingRecording(permissions.BasePermission):
    """Lecture : participant. Écriture : chair/secretary/recorded_by."""

    SAFE = permissions.SAFE_METHODS

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj = MeetingRecording
        meeting = obj.meeting
        if request.method in self.SAFE:
            return _is_participant(request.user, meeting) \
                or _is_chair_or_secretary(request.user, meeting)
        # Écriture
        if _is_chair_or_secretary(request.user, meeting):
            return True
        if obj.recorded_by_id == request.user.id:
            return True
        return False


class CanRecordOnMeeting(permissions.BasePermission):
    """Peut démarrer un enregistrement sur une réunion ?

    Tout participant officiel (la bêta n'impose pas chair only).
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        meeting_id = view.kwargs.get("meeting_id")
        if not meeting_id:
            return True  # /recordings/<id>/... checks à has_object_permission
        try:
            from apps.meetings.models import Meeting
            meeting = Meeting.unscoped.filter(id=meeting_id).first()
        except Exception:  # noqa: BLE001
            meeting = None
        if meeting is None:
            return False
        return (
            _is_participant(request.user, meeting)
            or _is_chair_or_secretary(request.user, meeting)
        )
