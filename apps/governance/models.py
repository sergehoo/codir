"""Apps governance — directions, départements, postes, organigramme."""
from django.db import models

from core.models import TenantAwareModel


class Direction(TenantAwareModel):
    """Direction fonctionnelle (DAF, DRH, DSI, DT...)."""

    subsidiary = models.ForeignKey(
        "organizations.Subsidiary",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="directions",
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, blank=True)
    head = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="directions_led")
    color = models.CharField(max_length=7, default="#475569")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "name"])]

    def __str__(self):
        return self.name


class Department(TenantAwareModel):
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=120)
    head = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="departments_led")

    class Meta:
        ordering = ["name"]


class Position(TenantAwareModel):
    LEVEL_CHOICES = [
        ("c_level", "C-Level"),
        ("vp", "VP"),
        ("director", "Director"),
        ("manager", "Manager"),
        ("ic", "Individual Contributor"),
    ]
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="positions")
    title = models.CharField(max_length=150)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="ic")
    holder = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="positions_held")
    is_executive_committee_member = models.BooleanField(default=False)

    class Meta:
        ordering = ["department", "level", "title"]


class OrgChartNode(TenantAwareModel):
    """Représentation arborescente pour le rendu d'organigramme."""

    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    order = models.PositiveIntegerField(default=0)
    target_type = models.CharField(max_length=20, choices=[
        ("direction", "Direction"), ("department", "Department"), ("position", "Position")
    ])
    target_id = models.UUIDField()
    collapsed = models.BooleanField(default=False)

    class Meta:
        ordering = ["parent_id", "order"]
