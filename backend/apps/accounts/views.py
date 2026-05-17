"""Views DRF — accounts (bêta : auth JWT + profil + memberships + annuaire)."""
import logging

from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.permissions import IsOrganizationMember

from .models import Membership, Role
from .serializers import (
    MembershipSerializer, RoleSerializer,
    TokenObtainPairWithOrgSerializer, UserMiniSerializer, UserSerializer,
)

User = get_user_model()
log = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    serializer_class = TokenObtainPairWithOrgSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        data["full_name"] = request.user.get_full_name() or request.user.email
        return Response(data)

    def patch(self, request):
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        out = ser.data
        out["full_name"] = request.user.get_full_name() or request.user.email
        return Response(out)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/me/change-password/

    Body : { current_password, new_password }
    Réponse : 200 { detail: 'Mot de passe modifié' } | 400 { current_password: [...] }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework import status as drf_status

        user = request.user
        current = request.data.get("current_password", "")
        new = request.data.get("new_password", "")

        if not current or not new:
            return Response(
                {"detail": "current_password et new_password requis."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(current):
            return Response(
                {"current_password": ["Mot de passe actuel incorrect."]},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        if new == current:
            return Response(
                {"new_password": ["Le nouveau mot de passe doit être différent de l'ancien."]},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        # Validation Django (longueur, complexité, etc.)
        try:
            validate_password(new, user=user)
        except DjangoValidationError as e:
            return Response(
                {"new_password": list(e.messages)},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        log.info("Password changed for user_id=%s", user.id)

        return Response({"detail": "Mot de passe modifié."}, status=drf_status.HTTP_200_OK)


class MyMembershipsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Membership.unscoped
            .filter(user=request.user, is_active=True)
            .select_related("organization")
        )
        return Response([
            {
                "organization_id": str(m.organization_id),
                "organization_name": m.organization.name,
                "organization_slug": m.organization.slug,
                "is_owner": m.is_owner,
                "is_executive": m.is_executive,
            } for m in qs
        ])


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Annuaire des utilisateurs (membres du tenant courant).

    Utilise `UserMiniSerializer` (avec `full_name`) — compatible avec le
    composant `UserSelect` du frontend. Pagination désactivée.
    """

    permission_classes = [IsOrganizationMember]
    serializer_class = UserMiniSerializer
    pagination_class = None

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            log.warning("UserViewSet.get_queryset: no tenant in request")
            return User.objects.none()
        try:
            user_ids = list(
                Membership.unscoped
                .filter(organization=org, is_active=True)
                .values_list("user_id", flat=True)
            )
            return (
                User.objects.filter(id__in=user_ids)
                .order_by("last_name", "first_name", "email")
            )
        except Exception as exc:
            log.exception("UserViewSet.get_queryset failed: %s", exc)
            return User.objects.none()


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """Liste des rôles du tenant courant.

    On utilise `get_queryset` (et pas `queryset = ...`) pour éviter une
    évaluation du `TenantManager` au moment de l'import du module (où
    `current_organization` est encore None).
    """

    permission_classes = [IsOrganizationMember]
    serializer_class = RoleSerializer
    pagination_class = None

    def get_queryset(self):
        return Role.objects.all()


class MembershipViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrganizationMember]
    serializer_class = MembershipSerializer

    def get_queryset(self):
        return (
            Membership.objects
            .select_related("user", "subsidiary", "organization")
            .prefetch_related("roles")
            .all()
        )
