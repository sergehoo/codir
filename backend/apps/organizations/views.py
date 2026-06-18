import logging

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsOrganizationMember

from .models import Organization, Subsidiary
from .serializers import OrganizationSerializer, SubsidiarySerializer

log = logging.getLogger(__name__)


def _can_admin_org(user, org) -> bool:
    """Vrai si le user est admin de l'org (owner / executive / superuser)."""
    if user.is_superuser:
        return True
    if org is None:
        return False
    membership = (
        user.memberships.filter(organization=org, is_active=True).first()
        if hasattr(user, "memberships") else None
    )
    if membership is None:
        return False
    return bool(membership.is_owner or membership.is_executive)


class CurrentOrgView(APIView):
    """GET : récupère l'org courante (tout membre actif).
    PATCH : modifie branding de l'org (owner / executive uniquement).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.organization is None:
            return Response({"detail": "Aucun tenant en contexte."}, status=400)
        return Response(OrganizationSerializer(request.organization).data)

    def patch(self, request):
        org = request.organization
        if org is None:
            return Response({"detail": "Aucun tenant en contexte."}, status=400)
        if not _can_admin_org(request.user, org):
            return Response(
                {"detail": "Réservé aux administrateurs de l'organisation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = OrganizationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except Exception as exc:  # noqa: BLE001
            log.exception("CurrentOrgView.patch failed")
            return Response(
                {"detail": f"Échec de la mise à jour : {type(exc).__name__}: {exc}"},
                status=500,
            )
        log.info(
            "Organization branding updated org=%s by=%s fields=%s",
            org.id, request.user.id, list(request.data.keys()),
        )
        return Response(serializer.data)


class SubsidiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = SubsidiarySerializer

    def get_queryset(self):
        """Filtre par tenant courant si défini, sinon bypass."""
        org = getattr(self.request, "organization", None)
        qs = Subsidiary.objects.all()
        if org is not None:
            qs = qs.filter(organization=org)
        return qs

    def list(self, request, *args, **kwargs):
        """Override pour catcher tout 500 imprévu et retourner un détail utilisable."""
        import logging
        log = logging.getLogger(__name__)
        try:
            return super().list(request, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("SubsidiaryViewSet.list failed")
            from rest_framework.response import Response
            return Response(
                {"detail": f"Erreur de chargement des filiales : {type(exc).__name__}: {exc}"},
                status=500,
            )
