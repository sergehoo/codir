"""ModelAdmin de base pour modèles multi-tenant.

Le manager par défaut (`TenantManager`) filtre par tenant courant ; Django
admin n'ayant pas de contexte tenant, on remplace le queryset par `unscoped`
afin que le superuser voie l'ensemble des données.
"""
from django.contrib import admin


class TenantAwareAdmin(admin.ModelAdmin):
    """Override `get_queryset` pour ignorer le tenant scope."""

    def get_queryset(self, request):
        return self.model.unscoped.all()
