"""Admin — AI engine : copilot conversations, RAG embeddings, journal d'inférence, glossaire."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import (
    AIConversation, AIDocumentEmbedding, AIGlossary, AIInferenceLog, AIMessage,
)


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    fields = ("role", "tokens", "feedback", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(AIConversation)
class AIConversationAdmin(TenantAwareAdmin):
    list_display = ("title", "user", "context_scope", "is_archived", "updated_at", "organization")
    list_filter = ("context_scope", "is_archived", "organization")
    search_fields = ("title", "user__email", "context_id")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("created_at", "updated_at")
    inlines = [AIMessageInline]


@admin.register(AIMessage)
class AIMessageAdmin(TenantAwareAdmin):
    list_display = ("conversation", "role", "tokens", "feedback", "created_at")
    list_filter = ("role", "feedback")
    search_fields = ("conversation__title", "content_md")
    autocomplete_fields = ("conversation", "organization")
    readonly_fields = ("created_at", "updated_at", "tokens")
    date_hierarchy = "created_at"


@admin.register(AIInferenceLog)
class AIInferenceLogAdmin(TenantAwareAdmin):
    """Journal immuable des appels IA — audit + observabilité."""

    list_display = ("created_at", "capability", "provider", "model", "actor",
                    "tokens_in", "tokens_out", "cost_usd", "latency_ms",
                    "cached", "success", "risk_class")
    list_filter = ("capability", "provider", "model", "success", "cached",
                   "risk_class", "organization")
    search_fields = ("capability", "provider", "model", "request_hash", "actor__email", "error")
    autocomplete_fields = ("actor", "organization")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(AIDocumentEmbedding)
class AIDocumentEmbeddingAdmin(TenantAwareAdmin):
    list_display = ("document", "chunk_index", "language", "model_version", "organization")
    list_filter = ("language", "model_version", "organization")
    search_fields = ("document__title", "content_text")
    autocomplete_fields = ("document", "organization")
    readonly_fields = ("created_at", "updated_at", "embedding")


@admin.register(AIGlossary)
class AIGlossaryAdmin(TenantAwareAdmin):
    list_display = ("term", "category", "added_by", "organization", "updated_at")
    list_filter = ("category", "organization")
    search_fields = ("term", "definition", "aliases")
    autocomplete_fields = ("added_by", "organization")
    readonly_fields = ("created_at", "updated_at")
