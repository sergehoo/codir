"""Apps notifications — module bêta CODIR complet.

In-app + email (extensible WhatsApp / SMS / Push).
Préférences utilisateur, anti-doublon rappels, log de transport.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TenantAwareModel, TimestampedModel


# ─── Enums ────────────────────────────────────────────────────

class NotificationLevel(models.TextChoices):
    INFO = "info", "Information"
    SUCCESS = "success", "Succès"
    WARNING = "warning", "Avertissement"
    DANGER = "danger", "Critique"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Faible"
    NORMAL = "normal", "Normale"
    HIGH = "high", "Élevée"
    CRITICAL = "critical", "Critique"


class NotificationChannel(models.TextChoices):
    INTERNAL = "internal", "Interne (in-app)"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    WHATSAPP = "whatsapp", "WhatsApp"
    PUSH = "push", "Push"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    SENT = "sent", "Envoyée"
    READ = "read", "Lue"
    FAILED = "failed", "Échec"
    SKIPPED = "skipped", "Ignorée"


class ReminderType(models.TextChoices):
    DAILY_USER = "daily_user", "Rappel quotidien utilisateur"
    WEEKLY_USER_DIGEST = "weekly_user_digest", "Synthèse hebdomadaire utilisateur"
    MANAGER_SUMMARY = "manager_summary", "Résumé manager"
    DUE_SOON = "due_soon", "Échéance proche"
    OVERDUE = "overdue", "Tâche en retard"


class ReminderTimeSlot(models.TextChoices):
    MORNING = "morning", "Matin"
    AFTERNOON = "afternoon", "Après-midi"
    ANYTIME = "anytime", "Quotidien"


class NotificationEvent(models.TextChoices):
    # Meetings
    MEETING_INVITED = "meeting_invited", "Invitation réunion"
    MEETING_REMINDER = "meeting_reminder", "Rappel réunion"
    MEETING_STARTED = "meeting_started", "Réunion démarrée"
    MEETING_COMPLETED = "meeting_completed", "Réunion clôturée"
    AGENDA_VALIDATED = "agenda_validated", "Ordre du jour validé"
    # Decisions
    DECISION_ASSIGNED = "decision_assigned", "Décision assignée"
    DECISION_APPROVED = "decision_approved", "Décision validée"
    DECISION_DEADLINE = "decision_deadline", "Échéance décision"
    DECISION_ACTION_DELAY = "decision_action_delay", "Décision en retard d'exécution"
    # Tasks / plans
    TASK_ASSIGNED = "task_assigned", "Tâche assignée"
    TASK_DELEGATED = "task_delegated", "Tâche déléguée"
    TASK_REMINDER = "task_reminder", "Rappel tâche"
    TASK_DEADLINE = "task_deadline", "Échéance tâche"
    TASK_DUE_SOON = "task_due_soon", "Échéance proche"
    TASK_OVERDUE = "task_overdue", "Tâche en retard"
    MANAGER_DAILY_SUMMARY = "manager_daily_summary", "Résumé manager"
    ACTION_PLAN_BLOCKED = "action_plan_blocked", "Plan d'action bloqué"
    ACTION_PLAN_COMPLETED = "action_plan_completed", "Plan d'action clôturé"
    PLAN_COMPLETED = "plan_completed", "Plan d'action clôturé (legacy)"
    # Gestion utilisateurs (admin)
    USER_CREATED = "user_created", "Bienvenue — compte créé"
    USER_PASSWORD_RESET = "user_password_reset", "Mot de passe réinitialisé"
    USER_REASSIGNED = "user_reassigned", "Affectation mise à jour"
    USER_DEACTIVATED = "user_deactivated", "Compte désactivé"
    USER_REACTIVATED = "user_reactivated", "Compte réactivé"
    # Digest hebdomadaire utilisateur (vendredi 9h)
    WEEKLY_USER_DIGEST = "weekly_user_digest", "Synthèse hebdomadaire des tâches"
    # Briefing matinal quotidien (envoyé selon daily_briefing_hour, default 7h)
    DAILY_BRIEFING = "daily_briefing", "Briefing matinal quotidien"


# ─── Notification ─────────────────────────────────────────────

class Notification(TenantAwareModel):
    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications",
    )
    # Périmètre filiale / direction — utile pour ciblage manager + filtres frontend
    subsidiary = models.ForeignKey(
        "organizations.Subsidiary", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="notifications",
    )
    direction = models.ForeignKey(
        "governance.Direction", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="notifications",
    )

    event = models.CharField(max_length=40, choices=NotificationEvent.choices, db_index=True)
    level = models.CharField(max_length=10, choices=NotificationLevel.choices, default=NotificationLevel.INFO)
    priority = models.CharField(
        max_length=10, choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL, db_index=True,
    )
    channel = models.CharField(
        max_length=10, choices=NotificationChannel.choices,
        default=NotificationChannel.INTERNAL, db_index=True,
    )
    status = models.CharField(
        max_length=10, choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING, db_index=True,
    )

    title = models.CharField(max_length=250)
    body = models.TextField(blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    action_url = models.CharField(
        max_length=500, blank=True,
        help_text="Lien profond frontend pour rebondir sur l'objet métier.",
    )

    target_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    target_id = models.CharField(max_length=80, blank=True)
    target = GenericForeignKey("target_type", "target_id")

    sent_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "seen_at"]),
            models.Index(fields=["organization", "event"]),
            models.Index(fields=["recipient", "channel", "status"]),
            models.Index(fields=["subsidiary", "event"]),
        ]

    def mark_read(self):
        from django.utils import timezone
        if self.seen_at is None:
            self.seen_at = timezone.now()
        self.read_at = timezone.now()
        self.status = NotificationStatus.READ
        self.save(update_fields=["seen_at", "read_at", "status", "updated_at"])


# ─── Préférences utilisateur ──────────────────────────────────

class NotificationPreference(TenantAwareModel):
    """Préférences fines par utilisateur (canaux + événements)."""
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="notification_preference",
    )

    # Canaux globaux
    email_enabled = models.BooleanField(default=True)
    internal_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=False)

    # Événements ciblés
    task_assignment_email = models.BooleanField(default=True)
    task_delegation_email = models.BooleanField(default=True)
    daily_task_reminder = models.BooleanField(default=True)
    manager_summary = models.BooleanField(default=True)
    due_soon_alert = models.BooleanField(default=True)
    overdue_alert = models.BooleanField(default=True)
    decision_alerts = models.BooleanField(default=True)
    meeting_alerts = models.BooleanField(default=True)

    # Agent IA proactif (Lot 2) — l'IA scrute les health_scores et envoie
    # des messages d'alerte dans le sidebar chat. Off-by-default-no : on
    # active par défaut pour démontrer la valeur, l'utilisateur peut couper.
    proactive_agent_enabled = models.BooleanField(default=True)

    # Briefing matinal quotidien (push + email à l'heure préférée).
    # Le service tourne toutes les heures et envoie aux users dont l'heure
    # locale courante == briefing_hour ET briefing_enabled=True.
    daily_briefing_enabled = models.BooleanField(default=True)
    daily_briefing_hour = models.PositiveSmallIntegerField(
        default=7,
        help_text="Heure locale (0-23) d'envoi du briefing matinal.",
    )

    # Heures de silence
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    locale = models.CharField(max_length=8, default="fr-FR")

    class Meta:
        indexes = [models.Index(fields=["user"])]


# ─── Log transport ────────────────────────────────────────────

class NotificationLog(TimestampedModel):
    """Trace technique d'un envoi (provider, code, payload réponse)."""
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="logs",
    )
    provider = models.CharField(max_length=40, help_text="smtp.hostinger / twilio / fcm / …")
    channel = models.CharField(max_length=10, choices=NotificationChannel.choices)
    status_code = models.CharField(max_length=20, blank=True)
    response = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["notification", "-created_at"]),
            models.Index(fields=["channel", "status_code"]),
        ]


# ─── Anti-doublon rappels ─────────────────────────────────────

class TaskReminderLog(TimestampedModel):
    """Empêche d'envoyer 2× le même rappel sur la même fenêtre.

    Clé logique : user + task + reminder_type + reminder_date + time_slot
    """
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="task_reminder_logs",
    )
    task = models.ForeignKey(
        "action_plans.ActionTask", null=True, blank=True,
        on_delete=models.CASCADE, related_name="reminder_logs",
    )
    reminder_type = models.CharField(max_length=20, choices=ReminderType.choices)
    reminder_date = models.DateField(db_index=True)
    time_slot = models.CharField(
        max_length=10, choices=ReminderTimeSlot.choices,
        default=ReminderTimeSlot.ANYTIME,
    )
    channel = models.CharField(max_length=10, choices=NotificationChannel.choices, default=NotificationChannel.EMAIL)
    status = models.CharField(max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.SENT)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reminder_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "task", "reminder_type", "reminder_date", "time_slot"],
                name="uniq_reminder_per_user_task_slot",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "reminder_type", "reminder_date"]),
        ]


# ─── Push Web (Lot 6 — PWA mobile) ─────────────────────────────

class PushSubscription(TenantAwareModel):
    """Abonnement Web Push d'un user sur un device/navigateur.

    Un user peut avoir plusieurs subscriptions (1 par device : iPhone + desktop
    + tablette par exemple). On les stocke toutes, on envoie à toutes les
    actives quand une notif `push_enabled=True` est émise.

    Spec : https://www.w3.org/TR/push-api/
    Champs requis : endpoint (URL FCM/Mozilla/WebKit), p256dh (clé pub), auth.
    """
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="push_subscriptions",
    )
    # Endpoint unique du push service (chrome → fcm.googleapis.com, firefox →
    # updates.push.services.mozilla.com, safari → web.push.apple.com).
    endpoint = models.URLField(max_length=600, db_index=True)
    p256dh = models.CharField(max_length=160)
    auth   = models.CharField(max_length=80)
    user_agent = models.CharField(max_length=300, blank=True)
    # Désactive si le push échoue avec 410 (gone) — l'utilisateur a unsubscribe
    # côté navigateur, plus la peine de tenter d'envoyer.
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_error  = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "endpoint"], name="uniq_user_endpoint",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"PushSub({self.user_id}, {self.endpoint[:40]}…)"
