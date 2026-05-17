"""Apps accounts — utilisateurs, MFA, sessions, RBAC (Role/Permission/Membership)."""
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models import TenantAwareModel, TimestampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email requis")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # email seul
    email = models.EmailField(unique=True)

    phone_e164 = models.CharField(max_length=20, blank=True)
    locale = models.CharField(max_length=10, default="fr-FR")
    timezone = models.CharField(max_length=50, default="Europe/Paris")
    avatar = models.URLField(blank=True)

    mfa_enabled = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20,
        blank=True,
        choices=[("totp", "TOTP"), ("webauthn", "WebAuthn"), ("push", "Push")],
    )
    last_mfa_at = models.DateTimeField(null=True, blank=True)

    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_geo = models.CharField(max_length=100, blank=True)
    must_change_password = models.BooleanField(default=False)
    is_executive = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name() or self.email}"

    # ─── Helpers filiale ──────────────────────────────────────────
    def subsidiary_ids_for(self, organization) -> set:
        """IDs des filiales actives auxquelles ce user appartient via Membership.

        Utilisé par les permissions et filtres : un user ne peut modifier
        que les ressources rattachées à l'une de SES filiales.
        Retourne un set (vide → user transverse Groupe sans filiale spécifique).
        """
        ids = (
            self.memberships
            .filter(organization=organization, is_active=True, subsidiary__isnull=False)
            .values_list("subsidiary_id", flat=True)
        )
        return set(ids)

    def primary_subsidiary_for(self, organization):
        """Première filiale active du user pour l'org donnée (ou None)."""
        m = (
            self.memberships
            .filter(organization=organization, is_active=True, subsidiary__isnull=False)
            .select_related("subsidiary")
            .first()
        )
        return m.subsidiary if m else None


class MFADevice(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_devices")
    name = models.CharField(max_length=80)
    method = models.CharField(max_length=20)
    secret_encrypted = models.BinaryField()  # chiffré côté service (Vault transit)
    last_used_at = models.DateTimeField(null=True, blank=True)
    confirmed = models.BooleanField(default=False)


class Session(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    jwt_jti = models.CharField(max_length=64, unique=True, db_index=True)
    ip = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    geo = models.CharField(max_length=100, blank=True)
    device_fingerprint = models.CharField(max_length=120, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"]), models.Index(fields=["expires_at"])]


class PasswordHistory(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_history")
    password_hash = models.CharField(max_length=255)


class InvitationToken(TenantAwareModel):
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    role_codes = models.JSONField(default=list)
    invited_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="invitations_sent")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)


# ─── RBAC ────────────────────────────────────────────────────────────


class Permission(TimestampedModel):
    """Permission atomique nommée `app:resource:action`."""

    code = models.CharField(max_length=120, unique=True)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_macro = models.BooleanField(default=False)
    children = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="parents")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Role(TenantAwareModel):
    """Rôle dans une organisation (tenant-scoped)."""

    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False, help_text="Rôle standard non supprimable")
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("organization", "code")]
        indexes = [models.Index(fields=["organization", "code"])]

    def __str__(self):
        return f"{self.name} [{self.organization.slug}]"


class Membership(TenantAwareModel):
    """Liaison user × organisation × rôles × filiale."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    # Filiale principale du collaborateur (null pour rôles transverses Groupe)
    subsidiary = models.ForeignKey(
        "organizations.Subsidiary",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="memberships",
        help_text="Filiale principale du collaborateur (null pour les rôles transverses Groupe).",
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="memberships")
    directions = models.ManyToManyField("governance.Direction", blank=True, related_name="memberships")
    departments = models.ManyToManyField("governance.Department", blank=True, related_name="memberships")
    is_owner = models.BooleanField(default=False)
    is_executive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="memberships_invited")

    class Meta:
        unique_together = [("organization", "user")]
        indexes = [
            models.Index(fields=["organization", "user", "is_active"]),
        ]
