"""Admin — budgets, lignes, scénarios, dépenses."""
from django.contrib import admin

from core.admin import TenantAwareAdmin

from .models import Budget, BudgetLine, BudgetScenario, BudgetSpend


class BudgetLineInline(admin.TabularInline):
    model = BudgetLine
    extra = 0
    fields = ("name", "category", "direction", "period", "planned_amount",
              "committed_amount", "spent_amount")
    autocomplete_fields = ("direction",)
    show_change_link = True


@admin.register(Budget)
class BudgetAdmin(TenantAwareAdmin):
    list_display = ("year", "name", "subsidiary", "currency", "status",
                    "approved_at", "approved_by", "organization")
    list_filter = ("year", "status", "currency", "organization")
    search_fields = ("name", "subsidiary__name")
    autocomplete_fields = ("subsidiary", "approved_by", "organization")
    readonly_fields = ("created_at", "updated_at", "approved_at")
    date_hierarchy = "created_at"
    inlines = [BudgetLineInline]


@admin.register(BudgetLine)
class BudgetLineAdmin(TenantAwareAdmin):
    list_display = ("name", "budget", "category", "direction", "period",
                    "planned_amount", "spent_amount", "variance_display")
    list_filter = ("period", "organization")
    search_fields = ("name", "category", "budget__name", "direction__name")
    autocomplete_fields = ("budget", "direction", "organization")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Écart")
    def variance_display(self, obj):
        v = obj.variance
        return f"{v:,.2f}" if v is not None else "—"


@admin.register(BudgetScenario)
class BudgetScenarioAdmin(TenantAwareAdmin):
    list_display = ("name", "base_budget", "status", "created_by", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "description", "base_budget__name")
    autocomplete_fields = ("base_budget", "created_by", "organization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(BudgetSpend)
class BudgetSpendAdmin(TenantAwareAdmin):
    list_display = ("budget_line", "amount", "currency", "vendor",
                    "spent_on", "source", "validated_by")
    list_filter = ("source", "currency", "spent_on")
    search_fields = ("vendor", "invoice_ref", "description",
                     "budget_line__name", "integration_external_id")
    autocomplete_fields = ("budget_line", "validated_by", "organization")
    date_hierarchy = "spent_on"
    readonly_fields = ("created_at", "updated_at")
