from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Agenda, AgendaItem, AgendaItemComment


class AgendaItemInline(admin.TabularInline):
    model = AgendaItem
    extra = 0
    autocomplete_fields = ("responsible",)
    fields = ("order", "title", "priority", "estimated_duration_minutes",
              "responsible", "status")


@admin.register(Agenda)
class AgendaAdmin(TenantAwareAdmin):
    list_display = ("meeting", "is_validated", "validated_at", "validated_by")
    list_filter = ("is_validated",)
    search_fields = ("meeting__title",)
    autocomplete_fields = ("meeting", "validated_by")
    readonly_fields = ("validated_at",)
    inlines = [AgendaItemInline]


@admin.register(AgendaItem)
class AgendaItemAdmin(TenantAwareAdmin):
    list_display = ("title", "agenda", "order", "priority", "status",
                    "estimated_duration_minutes", "responsible")
    list_filter = ("priority", "status")
    search_fields = ("title", "description_md")
    autocomplete_fields = ("agenda", "responsible")
    ordering = ("agenda", "order")


@admin.register(AgendaItemComment)
class AgendaItemCommentAdmin(TenantAwareAdmin):
    list_display = ("item", "author", "created_at")
    search_fields = ("body_md",)
    autocomplete_fields = ("item", "author")
