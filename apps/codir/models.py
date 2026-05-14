"""Apps codir — instance CODIR (structure formelle du Comité de Direction)."""
from django.db import models

from core.models import TenantAwareModel


class CodirInstance(TenantAwareModel):
    """Définition d'un Comité de Direction (CODIR Groupe / CODIR Filiale)."""

    FREQUENCY = [
        ("weekly", "Hebdomadaire"),
        ("biweekly", "Bimensuel"),
        ("monthly", "Mensuel"),
        ("quarterly", "Trimestriel"),
        ("ad_hoc", "Ad-hoc"),
    ]

    subsidiary = models.ForeignKey(
        "organizations.Subsidiary",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="codirs",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY, default="weekly")
    default_day_of_week = models.PositiveSmallIntegerField(default=1, help_text="0=lundi … 6=dimanche")
    default_time = models.TimeField()
    default_duration_minutes = models.PositiveIntegerField(default=120)
    quorum_min_members = models.PositiveIntegerField(default=5)
    chairperson = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="chair_of_codirs")
    secretary = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="secretary_of_codirs")
    permanent_members = models.ManyToManyField("accounts.User", blank=True, related_name="codir_memberships")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "is_active"])]


class CodirCharter(TenantAwareModel):
    codir = models.OneToOneField(CodirInstance, on_delete=models.CASCADE, related_name="charter")
    content_md = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    approved_at = models.DateTimeField(null=True, blank=True)
