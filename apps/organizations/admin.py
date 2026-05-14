from django.contrib import admin

from .models import Organization, Subsidiary


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "country", "currency", "is_active", "created_at")
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


@admin.register(Subsidiary)
class SubsidiaryAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "country", "currency", "is_active", "parent")
    list_filter = ("is_active", "country", "currency")
    search_fields = ("name", "siret")
    autocomplete_fields = ("organization", "parent")
    readonly_fields = ("id", "created_at", "updated_at")
