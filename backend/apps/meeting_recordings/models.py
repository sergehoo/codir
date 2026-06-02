"""Modèles meeting_recordings — pipeline audio → transcription → IA.

Architecture :
- MeetingRecording = source de vérité (1 réunion peut avoir N enregistrements,
  ex : pause/reprise crée un nouveau take ; ou bien plusieurs takes successifs
  en cas de reprise après crash navigateur).
- RecordingChunk = morceaux pour upload streamé (option v2, bêta = pas utilisé
  mais le modèle existe pour ne pas casser une migration future).
- SpeakerSegment = segments diarisés (1 ligne = 1 prise de parole continue).
- DetectedSpeaker = voix distincte agrégée (1 ligne = 1 SPEAKER_XX).
- SpeakerParticipantMapping = mapping confirmé voix → utilisateur.
- RecordingAIExtraction = brouillons IA (résumés, décisions, actions) en
  attente de validation manuelle avant d'être poussés dans decisions/action_plans.

Toutes les entités héritent de TenantAwareModel : isolation tenant automatique.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from core.models import TenantAwareModel, TimestampedModel


# ─── Enums ────────────────────────────────────────────────────

class RecordingStatus(models.TextChoices):
    CREATED = "created", "Créé"
    RECORDING = "recording", "En cours d'enregistrement"
    UPLOADING = "uploading", "Upload en cours"
    UPLOADED = "uploaded", "Upload terminé"
    PROCESSING = "processing", "Traitement initial"
    TRANSCRIBING = "transcribing", "Transcription en cours"
    DIARIZING = "diarizing", "Détection des voix"
    WAITING_SPEAKER_MAPPING = "waiting_speaker_mapping", "Attente identification des voix"
    GENERATING_FINAL_TRANSCRIPT = "generating_final_transcript", "Génération transcription finale"
    SUMMARIZING = "summarizing", "Résumé IA en cours"
    EXTRACTING_ACTIONS = "extracting_actions", "Extraction décisions/actions"
    COMPLETED = "completed", "Terminé"
    FAILED = "failed", "Échec"


# Statuts considérés "terminaux" (pas de retry auto).
RECORDING_FINAL_STATUSES = {
    RecordingStatus.COMPLETED,
    RecordingStatus.FAILED,
}


class AIExtractionType(models.TextChoices):
    SUMMARY = "summary", "Résumé exécutif"
    MINUTES = "minutes", "Compte rendu détaillé"
    DECISION = "decision", "Décision proposée"
    ACTION = "action", "Action proposée"
    RISK = "risk", "Risque mentionné"
    DEADLINE = "deadline", "Échéance détectée"
    BLOCKER = "blocker", "Point bloquant"
    QUESTION = "question", "Question reportée"


class AIExtractionStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    VALIDATED = "validated", "Validé"
    REJECTED = "rejected", "Rejeté"
    PUSHED = "pushed", "Poussé dans le module cible"


# ─── Helpers upload path ──────────────────────────────────────

def _audio_upload_path(instance, filename: str) -> str:
    """Chemin S3 du fichier audio : recordings/{org}/{year}/{recording_id}/{filename}.

    Forme une arborescence prévisible pour audit + nettoyage par rétention.
    """
    org_id = getattr(instance.organization_id, "hex", None) or instance.organization_id
    year = (instance.created_at.year if instance.created_at else "_pending")
    return f"recordings/{org_id}/{year}/{instance.id}/{filename}"


def _chunk_upload_path(instance, filename: str) -> str:
    rec = instance.recording
    org_id = getattr(rec.organization_id, "hex", None) or rec.organization_id
    return f"recordings/{org_id}/chunks/{rec.id}/{instance.index:04d}_{filename}"


def _speaker_sample_upload_path(instance, filename: str) -> str:
    rec = instance.recording
    org_id = getattr(rec.organization_id, "hex", None) or rec.organization_id
    return f"recordings/{org_id}/samples/{rec.id}/{instance.speaker_label}_{filename}"


# ─── MeetingRecording ─────────────────────────────────────────

class MeetingRecording(TenantAwareModel):
    """Un enregistrement audio attaché à une réunion CODIR.

    Le champ ``status`` reflète le cycle de vie complet (capture → IA → validation).
    """

    meeting = models.ForeignKey(
        "meetings.Meeting", on_delete=models.CASCADE, related_name="recordings",
    )
    recorded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recordings_made",
        help_text="Utilisateur qui a déclenché la capture (secrétaire/chair en général).",
    )

    title = models.CharField(max_length=250, blank=True)
    audio_file = models.FileField(
        upload_to=_audio_upload_path, max_length=600,
        null=True, blank=True,
        help_text="Fichier audio source (webm/ogg/wav/mp3). Vide tant qu'aucun upload.",
    )
    audio_normalized = models.FileField(
        upload_to=_audio_upload_path, max_length=600,
        null=True, blank=True,
        help_text="Version normalisée wav 16kHz mono (utilisée pour samples speakers).",
    )

    original_filename = models.CharField(max_length=300, blank=True)
    mime_type = models.CharField(max_length=80, blank=True)
    file_size = models.PositiveBigIntegerField(default=0, help_text="Octets")
    duration_seconds = models.FloatField(default=0)

    status = models.CharField(
        max_length=40, choices=RecordingStatus.choices,
        default=RecordingStatus.CREATED, db_index=True,
    )

    # ── Horodatages détaillés du pipeline ──
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # ── Transcripts à trois états (brut → speakers → final mappé) ──
    transcript_raw = models.TextField(
        blank=True,
        help_text="Sortie brute de transcription, sans speaker labels.",
    )
    transcript_with_speakers = models.JSONField(
        default=list, blank=True,
        help_text="Liste de segments [{speaker, start, end, text}, ...] avant mapping.",
    )
    transcript_final = models.JSONField(
        default=list, blank=True,
        help_text="Même format, mais avec speaker remplacé par display_name réel.",
    )

    # ── Sortie IA ──
    summary = models.TextField(blank=True, help_text="Résumé exécutif Markdown.")
    ai_minutes = models.TextField(
        blank=True,
        help_text="Compte rendu structuré Markdown (peut alimenter Meeting.final_notes_md).",
    )

    # ── Audit & sécurité ──
    consent_acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Quand l'utilisateur a confirmé l'information des participants.",
    )
    deleted_audio_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Si renseigné : l'audio brut a été purgé (rétention).",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "meeting", "-created_at"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "recorded_by"]),
        ]

    def __str__(self):
        return f"Recording {self.id} — {self.meeting_id} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in RECORDING_FINAL_STATUSES

    @property
    def is_processing(self) -> bool:
        return self.status not in (
            RecordingStatus.CREATED, RecordingStatus.RECORDING,
            RecordingStatus.COMPLETED, RecordingStatus.FAILED,
            RecordingStatus.WAITING_SPEAKER_MAPPING,
        )


# ─── RecordingChunk (option upload streamé v2) ────────────────

class RecordingChunk(TenantAwareModel):
    """Un morceau d'enregistrement uploadé pendant la capture (option avancée).

    En bêta, on n'utilise pas ce modèle (upload complet à l'arrêt). Il est
    posé pour permettre une migration v2 sans schema change.
    """

    recording = models.ForeignKey(
        MeetingRecording, on_delete=models.CASCADE, related_name="chunks",
    )
    chunk_file = models.FileField(upload_to=_chunk_upload_path, max_length=600)
    index = models.PositiveIntegerField(help_text="Ordre du chunk (0-based).")
    start_time = models.FloatField(default=0, help_text="Offset début (sec).")
    end_time = models.FloatField(default=0, help_text="Offset fin (sec).")
    size = models.PositiveBigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    checksum = models.CharField(max_length=64, blank=True, help_text="sha256 hex.")

    class Meta:
        ordering = ["recording_id", "index"]
        unique_together = [("recording", "index")]
        indexes = [models.Index(fields=["recording", "index"])]


# ─── SpeakerSegment ───────────────────────────────────────────

class SpeakerSegment(TenantAwareModel):
    """Segment diarisé : une plage [start, end] avec un speaker label."""

    recording = models.ForeignKey(
        MeetingRecording, on_delete=models.CASCADE, related_name="segments",
    )
    speaker_label = models.CharField(
        max_length=40, db_index=True,
        help_text="SPEAKER_00 / SPEAKER_01 / ... (avant mapping manuel).",
    )
    start_time = models.FloatField(help_text="Offset début dans l'audio (sec).")
    end_time = models.FloatField(help_text="Offset fin (sec).")
    text = models.TextField(blank=True)
    confidence = models.FloatField(
        default=0, help_text="Score confiance ASR (0..1) si fourni par le provider.",
    )
    # Extrait audio représentatif (snippet ~5-10 sec) — peuplé si nécessaire.
    audio_excerpt = models.FileField(
        upload_to=_speaker_sample_upload_path, max_length=600,
        null=True, blank=True,
    )

    class Meta:
        ordering = ["recording_id", "start_time"]
        indexes = [
            models.Index(fields=["recording", "start_time"]),
            models.Index(fields=["recording", "speaker_label"]),
        ]


# ─── DetectedSpeaker ──────────────────────────────────────────

class DetectedSpeaker(TenantAwareModel):
    """Voix distincte agrégée (1 ligne par SPEAKER_XX dans la réunion)."""

    recording = models.ForeignKey(
        MeetingRecording, on_delete=models.CASCADE, related_name="speakers",
    )
    speaker_label = models.CharField(max_length=40, db_index=True)
    display_name = models.CharField(
        max_length=200, blank=True,
        help_text="Nom affiché dans l'UI (au final = nom réel mappé).",
    )
    sample_audio = models.FileField(
        upload_to=_speaker_sample_upload_path, max_length=600,
        null=True, blank=True,
        help_text="Extrait audio représentatif pour écoute par l'utilisateur.",
    )
    total_segments = models.PositiveIntegerField(default=0)
    total_duration = models.FloatField(default=0, help_text="Secondes parlées au total.")
    confidence = models.FloatField(default=0)

    # Suggestion non-engageante : l'IA peut suggérer un participant probable
    # (fuzzy sur les noms cités), mais l'utilisateur valide manuellement.
    suggested_participant = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recording_suggestions",
    )
    mapped_participant = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recording_mappings",
    )
    is_confirmed = models.BooleanField(
        default=False,
        help_text="True quand l'utilisateur a explicitement validé l'association.",
    )

    class Meta:
        ordering = ["recording_id", "speaker_label"]
        unique_together = [("recording", "speaker_label")]
        indexes = [models.Index(fields=["recording", "is_confirmed"])]

    def __str__(self):
        return f"{self.speaker_label} → {self.mapped_participant or '?'}"


# ─── SpeakerParticipantMapping (audit du mapping) ─────────────

class SpeakerParticipantMapping(TenantAwareModel):
    """Historique des mappings : on garde toutes les versions (override = nouvelle ligne).

    Permet de retracer qui a mappé quoi quand, même après correction.
    """

    recording = models.ForeignKey(
        MeetingRecording, on_delete=models.CASCADE, related_name="mappings",
    )
    speaker_label = models.CharField(max_length=40, db_index=True)
    participant = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="speaker_mappings",
    )
    confirmed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="speaker_mappings_made",
    )
    confirmed_at = models.DateTimeField(auto_now_add=True)
    confidence = models.FloatField(default=1.0, help_text="1.0 si confirmé manuellement.")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["recording_id", "-confirmed_at"]
        indexes = [
            models.Index(fields=["recording", "speaker_label"]),
            models.Index(fields=["participant"]),
        ]


# ─── RecordingAIExtraction (brouillons à valider) ─────────────

class RecordingAIExtraction(TenantAwareModel):
    """Élément extrait par l'IA, en attente de validation manuelle.

    Workflow :
    1. Pipeline IA pose une ligne DRAFT.
    2. Utilisateur valide (status=VALIDATED) ou rejette (REJECTED).
    3. Sur validation décision/action, un objet réel est créé dans
       decisions/action_plans et lié via created_decision/created_action_plan.
    """

    recording = models.ForeignKey(
        MeetingRecording, on_delete=models.CASCADE, related_name="extractions",
    )
    extraction_type = models.CharField(
        max_length=20, choices=AIExtractionType.choices, db_index=True,
    )
    # JSON normalisé : contenu structuré (titre, description, responsable suggéré,
    # échéance, priorité, citations exactes de la transcription).
    raw_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=AIExtractionStatus.choices,
        default=AIExtractionStatus.DRAFT, db_index=True,
    )

    # Objets créés dans les modules cibles (uniquement après validation).
    created_decision = models.ForeignKey(
        "decisions.Decision", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="from_ai_extractions",
    )
    created_action_plan = models.ForeignKey(
        "action_plans.ActionPlan", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="from_ai_extractions",
    )

    validation_status = models.CharField(max_length=20, blank=True)
    validated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="ai_extractions_validated",
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["recording_id", "extraction_type", "-created_at"]
        indexes = [
            models.Index(fields=["recording", "extraction_type", "status"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.extraction_type} #{self.id} ({self.status})"
