"""TenantManager : filtrage automatique par tenant courant."""
from contextvars import ContextVar
from typing import Optional

from django.db import models

# ContextVar global accédé partout : middleware HTTP, TenantTask Celery, signals, etc.
current_organization: ContextVar[Optional[object]] = ContextVar("current_organization", default=None)


def set_current_tenant(org):
    return current_organization.set(org)


def get_current_tenant():
    return current_organization.get()


def reset_current_tenant(token):
    current_organization.reset(token)


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, organization):
        return self.filter(organization_id=organization.id)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Manager filtré tenant. Si aucun tenant en contexte, on retourne un queryset
    vide *par défaut* — préférer une exception bruyante en debug.
    """

    use_in_migrations = False

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        org = current_organization.get()
        if org is None:
            return qs.none()
        return qs.filter(organization_id=org.id)
