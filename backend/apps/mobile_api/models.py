"""Apps mobile_api — device push tokens et préférences spécifiques mobile."""
from django.db import models

from core.models import TenantAwareModel


class MobileDevice(TenantAwareModel):
    PLATFORM = [("ios", "iOS"), ("android", "Android"), ("huawei", "Huawei"), ("web", "Web PWA")]

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="mobile_devices")
    platform = models.CharField(max_length=10, choices=PLATFORM)
    push_token = models.CharField(max_length=400)  # FCM / APNs / WebPush endpoint
    device_model = models.CharField(max_length=120, blank=True)
    os_version = models.CharField(max_length=40, blank=True)
    app_version = models.CharField(max_length=40, blank=True)
    locale = models.CharField(max_length=10, default="fr-FR")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "push_token")]
        indexes = [models.Index(fields=["organization", "user"])]


class MobileSyncCursor(TenantAwareModel):
    """Curseurs delta-sync par utilisateur et par type de ressource."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="sync_cursors")
    resource_type = models.CharField(max_length=40)
    cursor = models.CharField(max_length=120, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "resource_type")]
