"""Apps organizations — tenant racine + filiales."""
import uuid

from django.db import models

from core.models import TimestampedModel


class Plan(models.TextChoices):
    ESSENTIAL = "essential", "Essential"
    ENTERPRISE = "enterprise", "Enterprise"
    SOVEREIGN = "sovereign", "Sovereign"


class Organization(TimestampedModel):
    """Tenant racine. Toute donnée métier est rattachée à une Organization."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    legal_form = models.CharField(max_length=80, blank=True)
    siret = models.CharField(max_length=20, blank=True)
    vat_number = models.CharField(max_length=40, blank=True)

    logo = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#2563eb")
    secondary_color = models.CharField(max_length=7, default="#0ea5e9")

    country = models.CharField(max_length=2, default="FR")
    timezone = models.CharField(max_length=50, default="Europe/Paris")
    currency = models.CharField(max_length=3, default="EUR")

    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.ESSENTIAL)
    is_active = models.BooleanField(default=True)

    sso_enforced = models.BooleanField(default=False)
    sso_provider = models.CharField(max_length=40, blank=True)

    data_residency = models.CharField(max_length=20, default="eu-west")
    suspended_at = models.DateTimeField(null=True, blank=True)

    # bypass tenant scoping (cas particulier : l'Organization elle-même)
    unscoped = models.Manager()
    objects = models.Manager()

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["is_active"])]

    def __str__(self):
        return self.name


class Subsidiary(TimestampedModel):
    """Filiale d'une Organization (entité juridique)."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="subsidiaries")
    name = models.CharField(max_length=200)
    legal_form = models.CharField(max_length=80, blank=True)
    siret = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2)
    currency = models.CharField(max_length=3)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    is_active = models.BooleanField(default=True)

    unscoped = models.Manager()
    objects = models.Manager()

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "name"])]

    def __str__(self):
        return f"{self.name} ({self.organization.slug})"
