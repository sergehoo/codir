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
    """Login en 2 étapes si l'utilisateur a MFA activé.

    Étape 1 (email + password) :
        - Si user.mfa_enabled = False → retourne {access, refresh} (flow normal)
        - Si user.mfa_enabled = True → retourne {mfa_required: True, challenge_token}
    Étape 2 (challenge_token + code TOTP) :
        - POST /auth/mfa/verify/ → retourne {access, refresh}
    """
    serializer_class = TokenObtainPairWithOrgSerializer

    def post(self, request, *args, **kwargs):
        from rest_framework import status as drf_status
        from . import mfa

        email = (request.data.get("email") or "").lower().strip()
        if not email:
            return super().post(request, *args, **kwargs)

        # Vérification password via serializer standard
        response = super().post(request, *args, **kwargs)
        if response.status_code != drf_status.HTTP_200_OK:
            return response

        # Password OK — check MFA
        user = User.objects.filter(email=email).first()
        if user and user.mfa_enabled and user.mfa_method == "totp":
            return Response({
                "mfa_required": True,
                "challenge_token": mfa.make_challenge_token(user.id),
                "method": "totp",
                "email": email,
            }, status=drf_status.HTTP_200_OK)

        return response


class MFASetupView(APIView):
    """POST /api/v1/auth/mfa/setup/

    Génère un secret TOTP + QR code. L'user doit ensuite appeler
    `/auth/mfa/verify-setup/` avec un code pour activer.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from . import mfa
        if request.user.mfa_enabled:
            return Response(
                {"detail": "MFA déjà activé. Désactivez d'abord pour reconfigurer."},
                status=400,
            )
        data = mfa.generate_setup(request.user)
        return Response(data)


class MFAVerifySetupView(APIView):
    """POST /api/v1/auth/mfa/verify-setup/  — body: {code}

    Vérifie le 1er code TOTP fourni après scan QR → active MFA.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from . import mfa
        code = (request.data.get("code") or "").strip()
        if not code or not code.isdigit() or len(code) != 6:
            return Response({"detail": "Code à 6 chiffres requis."}, status=400)
        if mfa.confirm_setup(request.user, code):
            return Response({"detail": "MFA activé.", "mfa_enabled": True})
        return Response(
            {"detail": "Code incorrect. Vérifiez l'heure de votre téléphone."},
            status=400,
        )


class MFALoginVerifyView(APIView):
    """POST /api/v1/auth/mfa/verify/

    Body: {challenge_token, code}
    Retourne {access, refresh} si code OK.
    """
    permission_classes = []  # public — l'user n'est pas encore authentifié

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from . import mfa

        token = request.data.get("challenge_token") or ""
        code = (request.data.get("code") or "").strip()
        if not token or not code:
            return Response(
                {"detail": "challenge_token et code requis."}, status=400,
            )

        user_id = mfa.verify_challenge_token(token)
        if not user_id:
            return Response(
                {"detail": "Session expirée. Reconnectez-vous."}, status=400,
            )

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"detail": "Utilisateur introuvable."}, status=400)

        if not mfa.verify_code(user, code):
            return Response({"detail": "Code MFA invalide."}, status=400)

        # Génère le JWT comme dans le login normal (avec org_id)
        refresh = RefreshToken.for_user(user)
        m = Membership.unscoped.filter(
            user=user, is_active=True,
        ).select_related("organization").first()
        if m:
            refresh["org_id"] = str(m.organization_id)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class MFADisableView(APIView):
    """POST /api/v1/auth/mfa/disable/  — body: {password}

    Désactive le MFA. Requiert confirmation du password pour sécurité.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from . import mfa
        password = request.data.get("password", "")
        if not request.user.check_password(password):
            return Response(
                {"detail": "Mot de passe incorrect."}, status=400,
            )
        mfa.disable_mfa(request.user)
        return Response({"detail": "MFA désactivé.", "mfa_enabled": False})


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
        """Limite aux memberships du tenant courant si présent."""
        org = getattr(self.request, "organization", None)
        qs = (
            Membership.unscoped
            .select_related("user", "subsidiary", "organization")
            .prefetch_related("roles")
            .all()
        )
        if org is not None:
            qs = qs.filter(organization=org)
        return qs

    def list(self, request, *args, **kwargs):
        """Override pour catcher tout 500 imprévu et retourner un détail utilisable."""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("MembershipViewSet.list failed")
            return Response(
                {"detail": f"Erreur de chargement des membres : {type(exc).__name__}: {exc}"},
                status=500,
            )
