"""Apps audit_logs — bêta : journal simple (sans signature cryptographique)."""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TenantAwareModel


class AuditAction(models.TextChoices):
    CREATED = "created", "Créé"
    UPDATED = "updated", "Mis à jour"
    DELETED = "deleted", "Supprimé"
    VALIDATED = "validated", "Validé"
    APPROVED = "approved", "Approuvé"
    CLOSED = "closed", "Clôturé"
    STARTED = "started", "Démarré"
    COMPLETED = "completed", "Terminé"
    CANCELLED = "cancelled", "Annulé"
    LOGIN = "login", "Connexion"
    LOGOUT = "logout", "Déconnexion"
    LOGIN_FAILED = "login_failed", "Échec de connexion"
    PASSWORD_RESET = "password_reset", "Réinitialisation mot de passe"
    USER_CREATED = "user_created", "Compte utilisateur créé"
    USER_DEACTIVATED = "user_deactivated", "Compte désactivé"
    USER_REACTIVATED = "user_reactivated", "Compte réactivé"
    USER_REASSIGNED = "user_reassigned", "Affectation mise à jour"
    CUSTOM = "custom", "Custom"


class AuditLog(TenantAwareModel):
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=AuditAction.choices, db_index=True)
    target_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    target_id = models.CharField(max_length=80, blank=True)
    target = GenericForeignKey("target_type", "target_id")
    target_repr = models.CharField(max_length=300, blank=True)

    description = models.CharField(max_length=400, blank=True)
    diff_json = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["target_type", "target_id", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]
