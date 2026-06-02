"""Views DRF — accounts (bêta : auth JWT + profil + memberships + annuaire)."""
import logging

from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.permissions import IsOrganizationMember, IsOrganizationOwner

from . import services as account_services
from .models import Membership, Role
from .serializers import (
    CreateMemberSerializer, MembershipSerializer,
    ReassignMembershipSerializer, RoleSerializer,
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


class UserViewSet(viewsets.ModelViewSet):
    """Annuaire + gestion administrative des utilisateurs du tenant.

    Lecture : tout membre. Écriture (create, deactivate, reset_password) :
    Owner de l'organisation uniquement (cf. `IsOrganizationOwner`).

    Endpoints :
    - GET    /auth/users/                       → liste annuaire (UserMini)
    - POST   /auth/users/                       → crée un user + membership + email credentials
    - GET    /auth/users/{id}/                  → détail (UserSerializer)
    - POST   /auth/users/{id}/reset-password/   → reset MDP + email
    - POST   /auth/users/{id}/deactivate/       → désactive + email
    - POST   /auth/users/{id}/reactivate/       → réactive + email
    """

    pagination_class = None

    def get_permissions(self):
        # SAFE methods (GET/HEAD/OPTIONS) → tout membre.
        # Écritures et actions admin → owner uniquement.
        if self.action in ("list", "retrieve"):
            return [IsOrganizationMember()]
        return [IsOrganizationOwner()]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateMemberSerializer
        if self.action == "retrieve":
            return UserSerializer
        return UserMiniSerializer

    def get_queryset(self):
        org = getattr(self.request, "organization", None)
        if org is None:
            log.warning("UserViewSet.get_queryset: no tenant in request")
            return User.objects.none()
        try:
            # Inclut les users désactivés (admin doit les voir pour réactiver).
            user_ids = list(
                Membership.unscoped
                .filter(organization=org)
                .values_list("user_id", flat=True)
            )
            return (
                User.objects.filter(id__in=user_ids)
                .order_by("last_name", "first_name", "email")
            )
        except Exception as exc:
            log.exception("UserViewSet.get_queryset failed: %s", exc)
            return User.objects.none()

    # ─── CREATE : user + membership + email ──────────────────

    def create(self, request, *args, **kwargs):
        ser = CreateMemberSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = getattr(request, "organization", None)
        if org is None:
            return Response({"detail": "Tenant requis."}, status=400)
        d = ser.validated_data

        # Résolution des FK / M2M par ID
        subsidiary = None
        if d.get("subsidiary"):
            from apps.organizations.models import Subsidiary
            subsidiary = Subsidiary.unscoped.filter(
                id=d["subsidiary"], organization=org,
            ).first()
            if subsidiary is None:
                return Response({"subsidiary": ["Filiale inconnue."]}, status=400)

        directions = []
        if d.get("direction_ids"):
            from apps.governance.models import Direction
            directions = list(Direction.unscoped.filter(
                id__in=d["direction_ids"], organization=org,
            ))

        try:
            user, membership, _raw = account_services.create_user_with_membership(
                organization=org, created_by=request.user,
                email=d["email"],
                first_name=d.get("first_name", ""),
                last_name=d.get("last_name", ""),
                phone_e164=d.get("phone_e164", ""),
                is_executive=d.get("is_executive", False),
                is_owner=d.get("is_owner", False),
                subsidiary=subsidiary,
                directions=directions,
                role_codes=d.get("role_codes") or None,
                send_welcome_email=d.get("send_welcome_email", True),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:  # noqa: BLE001
            log.exception("create_user_with_membership KO")
            return Response({"detail": f"Erreur : {exc}"}, status=500)

        # On renvoie le Membership complet (UI a déjà le pattern pour l'afficher)
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    # ─── Reset password ──────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        org = getattr(request, "organization", None)
        if org is None:
            return Response({"detail": "Tenant requis."}, status=400)
        try:
            account_services.reset_user_password(
                user=user, organization=org, actor=request.user,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("reset_user_password KO")
            return Response({"detail": f"Erreur : {exc}"}, status=500)
        return Response({"detail": "Mot de passe réinitialisé. Email envoyé."})

    # ─── Désactivation / Réactivation ────────────────────────

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        org = getattr(request, "organization", None)
        if user.id == request.user.id:
            return Response(
                {"detail": "Vous ne pouvez pas désactiver votre propre compte."},
                status=400,
            )
        account_services.deactivate_user(
            user=user, organization=org, actor=request.user,
        )
        return Response({"detail": "Compte désactivé."})

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        user = self.get_object()
        org = getattr(request, "organization", None)
        account_services.reactivate_user(
            user=user, organization=org, actor=request.user,
        )
        return Response({"detail": "Compte réactivé."})


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
    serializer_class = MembershipSerializer

    def get_permissions(self):
        # Lecture pour tout membre, écritures sensibles owner-only.
        if self.action in ("list", "retrieve"):
            return [IsOrganizationMember()]
        return [IsOrganizationOwner()]

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

    @action(detail=True, methods=["post"], url_path="reassign")
    def reassign(self, request, pk=None):
        """Met à jour le périmètre d'un Membership (filiale + directions + rôles).

        Notifie l'utilisateur que son affectation a été mise à jour.
        """
        membership = self.get_object()
        ser = ReassignMembershipSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org = membership.organization

        # Résolution FK / M2M
        subsidiary = membership.subsidiary
        if "subsidiary" in d:
            if d["subsidiary"] is None:
                subsidiary = None
            else:
                from apps.organizations.models import Subsidiary
                subsidiary = Subsidiary.unscoped.filter(
                    id=d["subsidiary"], organization=org,
                ).first()
                if subsidiary is None:
                    return Response({"subsidiary": ["Filiale inconnue."]}, status=400)

        directions = None
        if "direction_ids" in d:
            from apps.governance.models import Direction
            directions = list(Direction.unscoped.filter(
                id__in=d["direction_ids"], organization=org,
            ))

        try:
            account_services.reassign_membership(
                membership=membership, actor=request.user,
                subsidiary=subsidiary if "subsidiary" in d else None,
                directions=directions,
                role_codes=d.get("role_codes"),
                is_owner=d.get("is_owner"),
                is_executive=d.get("is_executive"),
                send_email=d.get("send_email", True),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("reassign_membership KO")
            return Response({"detail": f"Erreur : {exc}"}, status=500)

        return Response(MembershipSerializer(membership).data)
