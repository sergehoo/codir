from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Document, DocumentAttachment


@admin.register(Document)
class DocumentAdmin(TenantAwareAdmin):
    list_display = ("name", "mime", "size_bytes", "is_confidential",
                    "uploaded_by", "organization", "created_at")
    list_filter = ("is_confidential", "mime")
    search_fields = ("name",)
    autocomplete_fields = ("uploaded_by", "organization")
    readonly_fields = ("mime", "size_bytes", "created_at", "updated_at")


@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(TenantAwareAdmin):
    list_display = ("document", "target_type", "target_id", "label", "attached_by")
    list_filter = ("target_type",)
    search_fields = ("label",)
    autocomplete_fields = ("document", "attached_by")
