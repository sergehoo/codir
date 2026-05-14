from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(TenantAwareAdmin):
    list_display = ("action", "actor", "target_type", "target_repr",
                    "ip", "created_at", "organization")
    list_filter = ("action", "target_type", "organization")
    search_fields = ("description", "target_repr", "actor__email", "ip", "request_id")
    autocomplete_fields = ("actor", "organization")
    raw_id_fields = ("target_type",)
    readonly_fields = [f.name for f in AuditLog._meta.get_fields() if not f.is_relation or f.many_to_one]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False  # entries créées par signals uniquement

    def has_change_permission(self, request, obj=None):
        return False  # journal immuable

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
