"""Modèles meetings — version bêta CODIR."""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.common.enums import (
    AttendanceStatus, MeetingStatus, ParticipantRole,
)
from core.models import TenantAwareModel


class MeetingType(models.TextChoices):
    REGULAR = "regular", "Ordinaire"
    EXTRAORDINARY = "extraordinary", "Extraordinaire"
    STRATEGIC = "strategic", "Stratégique"
    CRISIS = "crisis", "De crise"


class Meeting(TenantAwareModel):
    """Réunion CODIR — bêta."""

    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=MeetingType.choices, default=MeetingType.REGULAR)

    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)

    location = models.CharField(max_length=300, blank=True, help_text="Lieu physique")
    video_url = models.URLField(blank=True, help_text="Lien Teams / Zoom / Meet")

    status = models.CharField(
        max_length=20, choices=MeetingStatus.choices,
        default=MeetingStatus.DRAFT, db_index=True,
    )

    chair = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="chaired_meetings",
    )
    secretary = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="kept_meetings",
    )

    quorum_min = models.PositiveIntegerField(default=0, help_text="Quorum requis (0 = pas de contrôle)")
    quorum_reached = models.BooleanField(default=False)

    final_notes_md = models.TextField(blank=True, help_text="Notes finales du secrétaire")
    minutes_doc = models.ForeignKey(
        "documents.Document", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="meetings_as_minutes",
    )
    minutes_generated_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="meetings_created",
    )

    class Meta:
        ordering = ["-scheduled_start"]
        indexes = [
            models.Index(fields=["organization", "scheduled_start"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["chair"]),
            models.Index(fields=["secretary"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.scheduled_start:%Y-%m-%d}"

    @property
    def is_locked(self) -> bool:
        return self.status in (MeetingStatus.COMPLETED, MeetingStatus.CANCELLED)

    @property
    def participants_count(self) -> int:
        return self.participants.count()

    @property
    def present_count(self) -> int:
        return self.attendances.filter(status=AttendanceStatus.PRESENT).count()


class MeetingParticipant(TenantAwareModel):
    """Participant officiel à une réunion (avec rôle)."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    external_email = models.EmailField(blank=True, null=True, help_text="Si invité externe")
    external_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=ParticipantRole.choices, default=ParticipantRole.MEMBER)
    is_required = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Contraintes d'unicité partielles : on n'applique l'unicité que
        # quand le champ est défini (sinon Postgres collisionne les "" / NULL).
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "user"],
                condition=models.Q(user__isnull=False),
                name="uniq_meeting_participant_user",
            ),
            models.UniqueConstraint(
                fields=["meeting", "external_email"],
                condition=models.Q(external_email__isnull=False),
                name="uniq_meeting_participant_external_email",
            ),
        ]
        indexes = [models.Index(fields=["meeting", "role"])]


class MeetingAttendance(TenantAwareModel):
    """Présence effective enregistrée par le secrétaire."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="attendances")
    participant = models.ForeignKey(MeetingParticipant, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.INVITED)
    arrived_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    comment = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="attendance_recorded",
    )

    class Meta:
        unique_together = [("meeting", "participant")]
        indexes = [models.Index(fields=["meeting", "status"])]


class MeetingNote(TenantAwareModel):
    """Notes prises pendant la réunion — ProseMirror JSON + texte plat + versionning."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    content_md = models.TextField(blank=True, help_text="Texte plat exporté (legacy / fallback).")
    content_json = models.JSONField(default=dict, blank=True, help_text="Document ProseMirror (Tiptap).")
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True, db_index=True)
    is_private = models.BooleanField(default=False)
    last_autosaved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version", "-updated_at"]
        indexes = [
            models.Index(fields=["meeting", "is_current"]),
            models.Index(fields=["meeting", "-version"]),
        ]


class DetectedDecisionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PUBLISHED = "published", "Publiée"
    DISMISSED = "dismissed", "Rejetée"


class MeetingDetectedDecision(TenantAwareModel):
    """Décision détectée par le parser — à valider avant publication."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="detected_decisions")
    note = models.ForeignKey(
        MeetingNote, on_delete=models.CASCADE, related_name="detected_decisions",
        null=True, blank=True,
    )
    title = models.CharField(max_length=400)
    raw_line = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=DetectedDecisionStatus.choices, default=DetectedDecisionStatus.PENDING)
    decision = models.OneToOneField(
        "decisions.Decision", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="detected_source",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="decisions_published",
    )

    class Meta:
        ordering = ["meeting", "order"]
        indexes = [models.Index(fields=["meeting", "status"])]


class MeetingDetectedAction(TenantAwareModel):
    """Action détectée par le parser — rattachée à une décision détectée."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="detected_actions")
    detected_decision = models.ForeignKey(
        MeetingDetectedDecision, on_delete=models.CASCADE,
        related_name="actions", null=True, blank=True,
    )
    title = models.CharField(max_length=400)
    raw_line = models.TextField(blank=True)
    assignee = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="detected_action_assignments",
    )
    assignee_mention = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=DetectedDecisionStatus.choices, default=DetectedDecisionStatus.PENDING)
    action_task = models.OneToOneField(
        "action_plans.ActionTask", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="detected_source",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="actions_published",
    )

    class Meta:
        ordering = ["meeting", "order"]
        indexes = [
            models.Index(fields=["meeting", "status"]),
            models.Index(fields=["detected_decision"]),
        ]


class MeetingMention(TenantAwareModel):
    """Mention @user dans les notes."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="mentions")
    user = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="meeting_mentions",
    )
    raw_text = models.CharField(max_length=200)
    occurrences = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["meeting", "-occurrences"]
        indexes = [models.Index(fields=["meeting", "user"])]
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "user"],
                condition=models.Q(user__isnull=False),
                name="uniq_meeting_user_mention",
            ),
        ]


class MeetingMinutes(TenantAwareModel):
    """Compte rendu simple généré à la clôture (snapshot HTML)."""

    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name="minutes")
    title = models.CharField(max_length=250)
    body_html = models.TextField()
    body_md = models.TextField(blank=True)
    generated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="minutes_generated",
    )
    document = models.ForeignKey(
        "documents.Document", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="meeting_minutes_doc",
    )
