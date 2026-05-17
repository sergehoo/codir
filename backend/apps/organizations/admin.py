from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Organization, Subsidiary


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name", "slug", "plan", "country", "currency", "is_active",
        "subsidiaries_count", "members_count", "created_at",
    )
    list_filter = ("plan", "is_active", "country", "currency")
    search_fields = ("name", "slug", "siret", "vat_number")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Identité", {"fields": ("id", "name", "slug", "legal_form", "siret", "vat_number")}),
        ("Branding", {"fields": ("logo", "primary_color", "secondary_color")}),
        ("Localisation", {"fields": ("country", "timezone", "currency")}),
        ("Abonnement", {"fields": ("plan", "is_active", "data_residency", "suspended_at")}),
        ("SSO", {"fields": ("sso_enforced", "sso_provider")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Filiales")
    def subsidiaries_count(self, obj):
        return obj.subsidiaries.count()

    @admin.display(description="Membres")
    def members_count(self, obj):
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(organization=obj).count()


@admin.register(Subsidiary)
class SubsidiaryAdmin(admin.ModelAdmin):
    list_display = (
        "name", "organization", "country", "currency",
        "is_active", "parent", "members_link",
    )
    list_filter = ("is_active", "country", "currency", "organization")
    search_fields = ("name", "siret")
    autocomplete_fields = ("organization", "parent")
    readonly_fields = ("id", "created_at", "updated_at", "members_link")

    fieldsets = (
        ("Identité", {"fields": ("id", "name", "legal_form", "siret")}),
        ("Hiérarchie", {"fields": ("organization", "parent")}),
        ("Localisation", {"fields": ("country", "currency")}),
        ("Statut", {"fields": ("is_active",)}),
        ("Membres", {"fields": ("members_link",)}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Collaborateurs")
    def members_link(self, obj):
        """Lien direct vers la liste Membership filtrée sur cette filiale."""
        n = obj.memberships.count()
        if n == 0:
            return format_html('<span style="color:#999">0 collaborateur</span>')
        url = reverse("admin:accounts_membership_changelist") + f"?subsidiary__id__exact={obj.pk}"
        return format_html('<a href="{}">{} collaborateur(s) →</a>', url, n)
