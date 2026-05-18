"""Admin — intégrations externes (M365, SAP, Power BI, etc.), webhooks."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    Integration, IntegrationCredential, IntegrationSyncRun,
    Webhook, WebhookDelivery,
)


@admin.register(Integration)
class IntegrationAdmin(TenantAwareAdmin):
    list_display = ("name", "provider", "auth_type", "is_active",
                    "last_sync_at", "organization")
    list_filter = ("provider", "auth_type", "is_active", "organization")
    search_fields = ("name", "provider")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at", "last_sync_at", "last_error")


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(TenantAwareAdmin):
    list_display = ("integration", "expires_at", "organization")
    autocomplete_fields = ("integration", "organization")
    # Les champs encrypted ne doivent jamais s'afficher en clair
    exclude = ("secret_encrypted", "refresh_token_encrypted")
    readonly_fields = ("created_at", "updated_at", "expires_at")


@admin.register(IntegrationSyncRun)
class IntegrationSyncRunAdmin(TenantAwareAdmin):
    list_display = ("integration", "scope", "status", "started_at", "completed_at",
                    "records_in", "records_out", "organization")
    list_filter = ("status", "integration__provider", "organization")
    search_fields = ("integration__name", "scope")
    autocomplete_fields = ("integration", "organization")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at",
                       "records_in", "records_out", "errors_json")
    date_hierarchy = "created_at"


@admin.register(Webhook)
class WebhookAdmin(TenantAwareAdmin):
    list_display = ("event", "target_url", "is_active", "organization")
    list_filter = ("event", "is_active", "organization")
    search_fields = ("event", "target_url")
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(TenantAwareAdmin):
    list_display = ("webhook", "event", "status", "response_code", "attempts",
                    "next_attempt_at", "organization")
    list_filter = ("status", "response_code", "organization")
    search_fields = ("event", "webhook__event", "webhook__target_url")
    autocomplete_fields = ("webhook", "organization")
    readonly_fields = ("created_at", "updated_at", "payload", "response_body")
    date_hierarchy = "created_at"
