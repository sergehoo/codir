"""Serializers DRF — accounts (bêta)."""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Membership, Role

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "avatar", "is_executive"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name",
            "phone_e164", "locale", "timezone", "avatar",
            "is_executive", "mfa_enabled",
            "date_joined", "last_login",
        ]
        read_only_fields = ("id", "date_joined", "last_login", "mfa_enabled")


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system"]


class MembershipSerializer(serializers.ModelSerializer):
    user_detail = UserMiniSerializer(source="user", read_only=True)
    role_codes = serializers.SlugRelatedField(
        source="roles", many=True, slug_field="code", read_only=True,
    )
    subsidiary_name = serializers.SerializerMethodField()

    def get_subsidiary_name(self, obj):
        """Tolère l'absence du champ `subsidiary` si la migration n'est pas
        encore appliquée (fail-safe pour les déploiements en cours)."""
        try:
            sub = getattr(obj, "subsidiary", None)
            return sub.name if sub else None
        except Exception:  # noqa: BLE001
            return None

    class Meta:
        model = Membership
        fields = [
            "id", "user", "user_detail", "is_owner", "is_executive",
            "is_active", "expires_at", "role_codes",
            "subsidiary", "subsidiary_name",
        ]
        extra_kwargs = {
            "subsidiary": {"required": False, "allow_null": True},
        }


class TokenObtainPairWithOrgSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # On injecte la première Organization membre
        m = Membership.unscoped.filter(user=user, is_active=True).select_related("organization").first()
        if m:
            token["org_id"] = str(m.organization_id)
        return token
