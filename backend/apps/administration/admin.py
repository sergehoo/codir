"""Admin — paramétrage tenant, AI config, feature flags, plans, facturation."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    AIConfiguration, FeatureFlag, Invoice, Plan, TenantSettings,
)


@admin.register(TenantSettings)
class TenantSettingsAdmin(TenantAwareAdmin):
    list_display = ("organization", "data_retention_days", "audit_retention_days", "updated_at")
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIConfiguration)
class AIConfigurationAdmin(TenantAwareAdmin):
    list_display = ("organization", "default_provider", "sovereign_mode",
                    "data_residency", "max_monthly_spend_usd")
    list_filter = ("default_provider", "sovereign_mode", "zero_retention")
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(TenantAwareAdmin):
    list_display = ("key", "enabled", "rollout_percent", "organization", "updated_at")
    list_filter = ("enabled", "organization")
    search_fields = ("key", "description")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Plan)
class PlanAdmin(TenantAwareAdmin):
    list_display = ("code", "name", "monthly_price_eur", "annual_price_eur",
                    "seat_limit", "is_active", "organization")
    list_filter = ("is_active", "organization")
    search_fields = ("code", "name", "description")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(TenantAwareAdmin):
    list_display = ("number", "period_start", "period_end", "amount_excl_tax",
                    "currency", "status", "organization")
    list_filter = ("status", "currency", "organization")
    search_fields = ("number", "stripe_invoice_id")
    autocomplete_fields = ("organization", "pdf_doc")
    date_hierarchy = "period_start"
    readonly_fields = ("created_at", "updated_at", "issued_at", "paid_at")
