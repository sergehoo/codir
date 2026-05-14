"""Permissions DRF partagées bêta."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOrganizationMember(BasePermission):
    """Empêche tout accès si l'utilisateur n'appartient pas au tenant courant."""

    message = "Vous n'êtes pas membre de cette organisation."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if org is None:
            return False
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=request.user, organization=org, is_active=True
        ).exists()


class IsOwnerOrReadOnly(BasePermission):
    """L'objet doit avoir un champ `created_by` / `owner` / `responsible` pour SAFE; sinon owner only."""

    owner_fields = ("created_by", "owner", "responsible", "assignee", "user")

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        for f in self.owner_fields:
            if hasattr(obj, f) and getattr(obj, f) == request.user:
                return True
        return False


class IsAdminOrReadOnly(BasePermission):
    """Lecture pour tous les membres, écriture pour staff/admin tenant."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, "is_executive", False)
        ))


class CanModifyMeeting(BasePermission):
    """Une réunion terminée est verrouillée sauf pour staff."""

    message = "La réunion est verrouillée car terminée ou annulée."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.status not in {"completed", "cancelled"}
