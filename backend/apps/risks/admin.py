"""Admin — cartographie risques, mitigations, incidents, conformité."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Compliance, Incident, Risk, RiskAssessment, RiskMitigation


class RiskAssessmentInline(admin.TabularInline):
    model = RiskAssessment
    extra = 0
    fields = ("review_date", "assessor", "impact", "probability", "comments")
    autocomplete_fields = ("assessor",)
    show_change_link = True


class RiskMitigationInline(admin.TabularInline):
    model = RiskMitigation
    extra = 0
    fields = ("title", "status", "action_plan",
              "target_residual_impact", "target_residual_probability")
    autocomplete_fields = ("action_plan",)
    show_change_link = True


@admin.register(Risk)
class RiskAdmin(TenantAwareAdmin):
    list_display = ("ref", "title", "category", "severity",
                    "impact", "probability", "status", "owner",
                    "direction", "organization")
    list_filter = ("category", "status", "organization", "direction")
    search_fields = ("ref", "title", "description_md")
    autocomplete_fields = ("owner", "direction", "organization")
    readonly_fields = ("created_at", "updated_at", "severity",
                       "detected_at", "closed_at")
    date_hierarchy = "created_at"
    inlines = [RiskAssessmentInline, RiskMitigationInline]
    fieldsets = (
        ("Identification", {"fields": ("ref", "title", "description_md", "category")}),
        ("Évaluation", {
            "fields": ("impact", "probability", "severity"),
            "description": "Severity = impact × probability (auto-calculé)",
        }),
        ("Gouvernance", {"fields": ("status", "owner", "direction", "organization")}),
        ("Timeline", {"fields": ("detected_at", "closed_at"), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(TenantAwareAdmin):
    list_display = ("risk", "review_date", "assessor", "impact", "probability")
    search_fields = ("risk__ref", "risk__title", "comments")
    autocomplete_fields = ("risk", "assessor", "organization")
    date_hierarchy = "review_date"
    readonly_fields = ("created_at", "updated_at")


@admin.register(RiskMitigation)
class RiskMitigationAdmin(TenantAwareAdmin):
    list_display = ("title", "risk", "status", "action_plan")
    list_filter = ("status",)
    search_fields = ("title", "description_md", "risk__ref")
    autocomplete_fields = ("risk", "action_plan", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Incident)
class IncidentAdmin(TenantAwareAdmin):
    list_display = ("title", "risk", "severity", "detected_at",
                    "resolved_at", "impact_financial", "organization")
    list_filter = ("severity", "organization")
    search_fields = ("title", "description_md", "risk__ref")
    autocomplete_fields = ("risk", "organization")
    date_hierarchy = "detected_at"
    readonly_fields = ("created_at", "updated_at")


@admin.register(Compliance)
class ComplianceAdmin(TenantAwareAdmin):
    list_display = ("framework", "requirement", "status",
                    "next_audit", "responsible", "organization")
    list_filter = ("status", "framework", "organization")
    search_fields = ("framework", "requirement")
    autocomplete_fields = ("responsible", "evidence_doc", "organization")
    date_hierarchy = "next_audit"
    readonly_fields = ("created_at", "updated_at")
