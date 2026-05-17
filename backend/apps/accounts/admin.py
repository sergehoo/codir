from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.html import format_html

from core.admin import TenantAwareAdmin

from .models import (
    InvitationToken, MFADevice, Membership, PasswordHistory,
    Permission, Role, Session, User,
)


# ─── Inline : Memberships sur la page User ────────────────────────────
class MembershipInline(admin.TabularInline):
    model = Membership
    # ⚠ Membership a 2 FK vers User (`user` et `invited_by`) — préciser laquelle
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("organization", "subsidiary")
    fields = (
        "organization", "subsidiary",
        "is_owner", "is_executive", "is_active", "expires_at",
    )
    verbose_name = "Appartenance"
    verbose_name_plural = "Appartenances (organisation × filiale)"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email", "first_name", "last_name",
        "subsidiaries_display", "is_executive",
        "mfa_enabled", "is_staff", "is_superuser", "last_login",
    )
    list_filter = (
        "is_executive", "is_staff", "is_superuser", "mfa_enabled", "is_active",
        "memberships__subsidiary",
    )
    search_fields = (
        "email", "first_name", "last_name", "phone_e164",
        "memberships__subsidiary__name",
    )
    ordering = ("last_name", "first_name")
    readonly_fields = (
        "id", "date_joined", "last_login", "last_login_ip", "last_login_geo", "last_mfa_at",
    )
    inlines = [MembershipInline]
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "phone_e164", "avatar")}),
        ("Préférences", {"fields": ("locale", "timezone")}),
        ("Sécurité", {"fields": ("mfa_enabled", "mfa_method", "last_mfa_at",
                                  "must_change_password", "is_executive")}),
        ("Permissions Django", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Audit", {"fields": ("date_joined", "last_login", "last_login_ip", "last_login_geo")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2",
                                                  "first_name", "last_name", "is_executive")}),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .prefetch_related("memberships__subsidiary")
        )

    @admin.display(description="Filiale(s)")
    def subsidiaries_display(self, obj):
        """Liste des filiales du user (via memberships actifs)."""
        names = sorted({
            m.subsidiary.name
            for m in obj.memberships.all()
            if m.is_active and m.subsidiary_id
        })
        if not names:
            return format_html('<span style="color:#999">— Groupe transverse —</span>')
        return ", ".join(names)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_macro")
    list_filter = ("is_macro",)
    search_fields = ("code", "label", "description")
    filter_horizontal = ("children",)


@admin.register(Role)
class RoleAdmin(TenantAwareAdmin):
    list_display = ("code", "name", "organization", "is_system")
    list_filter = ("is_system", "organization")
    search_fields = ("code", "name")
    filter_horizontal = ("permissions",)
    autocomplete_fields = ("organization",)


@admin.register(Membership)
class MembershipAdmin(TenantAwareAdmin):
    list_display = (
        "user", "organization", "subsidiary",
        "is_owner", "is_executive", "is_active", "expires_at",
    )
    list_filter = (
        "is_owner", "is_executive", "is_active",
        "organization", "subsidiary",
    )
    list_select_related = ("user", "organization", "subsidiary")
    search_fields = (
        "user__email", "user__first_name", "user__last_name",
        "subsidiary__name",
    )
    autocomplete_fields = ("user", "organization", "subsidiary", "invited_by")
    filter_horizontal = ("roles", "directions", "departments")
    fieldsets = (
        ("Identité", {"fields": ("user", "organization", "subsidiary")}),
        ("Rôles & Périmètre", {"fields": ("roles", "directions", "departments")}),
        ("Statut", {"fields": ("is_owner", "is_executive", "is_active", "expires_at")}),
        ("Invitation", {"fields": ("invited_by",)}),
    )


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "method", "confirmed", "last_used_at")
    list_filter = ("method", "confirmed")
    search_fields = ("user__email", "name")
    autocomplete_fields = ("user",)
    readonly_fields = ("secret_encrypted",)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip", "geo", "expires_at", "revoked_at", "created_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__email", "jwt_jti", "ip")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    readonly_fields = ("password_hash", "created_at")


@admin.register(InvitationToken)
class InvitationTokenAdmin(TenantAwareAdmin):
    list_display = ("email", "organization", "invited_by", "accepted_at", "expires_at")
    search_fields = ("email", "token")
    autocomplete_fields = ("organization", "invited_by")
    readonly_fields = ("token",)
