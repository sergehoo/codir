"""Permissions DRF — qui peut voir / modifier un enregistrement ?

Règles métier (bêta CODIR) :
- Lecture (list / retrieve / status / segments / extractions) :
  tout membre actif de l'organisation propriétaire de la réunion.
- Écriture (start / upload / mapping voix / validation IA) :
  tout membre actif de l'organisation (la bêta privilégie la simplicité —
  les actions sont auditées + tracées via `recorded_by` et audit_logs).
- Garde-fou : si le user n'est PAS membre actif de l'org, accès refusé
  (isolation tenant systématique).

Pourquoi pas plus strict ?
- Cas d'usage CODIR : le secrétaire peut être en retard, un délégué prend
  l'audio à sa place ; un Owner peut tester depuis son compte sans être
  participant officiel ; les permissions doivent rester pragmatiques.
- Pour resserrer en prod : ajouter un setting `RECORDING_RESTRICT_TO_PARTICIPANTS=True`
  qui réactive le check participant officiel + chair/secretary.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework import permissions


def _is_org_member(user, organization) -> bool:
    """True si user a un Membership actif sur l'organisation donnée."""
    if not user.is_authenticated or organization is None:
        return False
    try:
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=user, organization=organization, is_active=True,
        ).exists()
    except Exception:  # noqa: BLE001
        return False


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


def _is_org_owner(user, organization) -> bool:
    """True si user est Owner (DG) de l'organisation (membership.is_owner)."""
    if not user.is_authenticated or organization is None:
        return False
    try:
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=user, organization=organization, is_active=True, is_owner=True,
        ).exists()
    except Exception:  # noqa: BLE001
        return False


# Flag pour resserrer la sécurité en prod si besoin (default = False = ouvert).
_STRICT = getattr(settings, "RECORDING_RESTRICT_TO_PARTICIPANTS", False)


class CanAccessMeetingRecording(permissions.BasePermission):
    """Permission objet sur un MeetingRecording.

    Lecture : tout membre actif de l'org propriétaire de la réunion.
    Écriture : Owner OU chair/secretary OU `recorded_by` (auteur).
    """

    message = "Vous n'avez pas accès à cet enregistrement."

    def has_permission(self, request, view):
        # has_object_permission fait le check fin ; ici on demande juste auth.
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj = MeetingRecording — on récupère l'org via la réunion.
        meeting = obj.meeting
        organization = meeting.organization

        # 1. Garde-fou tenant : il faut être membre de l'org de la réunion.
        if not _is_org_member(request.user, organization):
            return False

        # 2. Lecture (SAFE) : tout membre actif suffit.
        if request.method in permissions.SAFE_METHODS:
            return True

        # 3. Écriture : Owner OU chair/secretary OU auteur du recording.
        if _is_org_owner(request.user, organization):
            return True
        if _is_chair_or_secretary(request.user, meeting):
            return True
        if obj.recorded_by_id == request.user.id:
            return True
        # En mode strict : on rejette ; en mode bêta : on autorise les participants.
        if _STRICT:
            return False
        return _is_participant(request.user, meeting)


class CanRecordOnMeeting(permissions.BasePermission):
    """Permission pour démarrer/uploader un enregistrement sur une réunion.

    Règle bêta : tout membre actif de l'organisation propriétaire de la
    réunion peut enregistrer (pragmatique, audité côté `recorded_by`).

    Mode strict (`RECORDING_RESTRICT_TO_PARTICIPANTS=True`) : seuls les
    participants officiels + chair/secretary peuvent enregistrer.
    """

    message = "Vous devez être membre de l'organisation de cette réunion pour enregistrer."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Pour les actions sans meeting_id en kwargs (cas /recordings/<id>/...),
        # on laisse passer — has_object_permission gère le détail.
        meeting_id = view.kwargs.get("meeting_id")
        if not meeting_id:
            return True

        # Lookup de la réunion sans contrainte tenant (l'isolation est faite
        # juste après en vérifiant le membership sur l'org de la réunion).
        try:
            from apps.meetings.models import Meeting
            meeting = Meeting.unscoped.filter(id=meeting_id).first()
        except Exception:  # noqa: BLE001
            return False
        if meeting is None:
            return False

        # Isolation tenant explicite
        if not _is_org_member(request.user, meeting.organization):
            return False

        # SAFE methods : tout membre suffit (lecture liste, etc.)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Mode strict : restreint aux participants officiels.
        if _STRICT:
            return (
                _is_org_owner(request.user, meeting.organization)
                or _is_chair_or_secretary(request.user, meeting)
                or _is_participant(request.user, meeting)
            )

        # Mode bêta : tout membre actif de l'org peut enregistrer.
        return True
