"""Permissions dédiées audit_logs : lecture admin-only (DG / Owner / Staff)."""
from rest_framework.permissions import BasePermission


class IsOrganizationAdmin(BasePermission):
    """Lecture & écriture réservées au DG/Owner du tenant, ou aux staff Django.

    Contrairement à `IsOrganizationOwner` (qui laisse passer toute lecture aux
    membres), cette permission verrouille AUSSI les GET — c'est essentiel pour
    les logs : seuls les admins doivent pouvoir consulter l'historique global.
    """

    message = "Consultation des logs réservée aux administrateurs de l'organisation."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        org = getattr(request, "organization", None)
        if org is None:
            return False
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=request.user, organization=org, is_active=True, is_owner=True,
        ).exists()
