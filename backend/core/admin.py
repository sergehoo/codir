"""ModelAdmin de base pour modèles multi-tenant.

Le manager par défaut (`TenantManager`) filtre par tenant courant ; Django
admin n'ayant pas de contexte tenant, on remplace le queryset par `unscoped`
afin que le superuser voie l'ensemble des données.
"""
from django.contrib import admin


class TenantAwareAdmin(admin.ModelAdmin):
    """Override `get_queryset` pour ignorer le tenant scope.

    Surcharge aussi les querysets utilisés pour valider les FK et M2M dans
    les formulaires : sans ça, la sauvegarde déclenche systématiquement
    « Sélectionnez un choix valide. Ce choix ne fait pas partie de ceux
    disponibles. » dès que le modèle lié hérite de `TenantAwareModel`
    (parce que son default manager renvoie `.none()` hors contexte tenant).
    """

    # ─── Lecture liste admin (déjà OK) ──────────────────────────
    def get_queryset(self, request):
        return self.model.unscoped.all()

    # ─── ForeignKey : utilise `unscoped` pour la validation ─────
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if "queryset" not in kwargs:
            target = db_field.remote_field.model
            qs = getattr(target, "unscoped", None)
            if qs is not None:
                kwargs["queryset"] = qs.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # ─── ManyToMany : idem ──────────────────────────────────────
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if "queryset" not in kwargs:
            target = db_field.remote_field.model
            qs = getattr(target, "unscoped", None)
            if qs is not None:
                kwargs["queryset"] = qs.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)
