"""RecordingService — création, upload, transitions de statut.

Toutes les fonctions sont idempotentes : on peut les rejouer sans casser
l'état métier (utile pour Celery retry).
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ..models import MeetingRecording, RecordingStatus


def create_recording(
    *, meeting, recorded_by, title: str = "",
    consent_acknowledged: bool = False,
) -> MeetingRecording:
    """Crée un MeetingRecording vide en statut CREATED.

    Le fichier audio est attaché ultérieurement par `mark_uploaded()`.
    """
    rec = MeetingRecording(
        organization=meeting.organization,
        meeting=meeting,
        recorded_by=recorded_by,
        title=title or f"Enregistrement {meeting.title}"[:250],
        status=RecordingStatus.CREATED,
        started_at=timezone.now(),
    )
    if consent_acknowledged:
        rec.consent_acknowledged_at = timezone.now()
    rec.save()
    return rec


def update_status(
    recording: MeetingRecording, status: str, *, error: str = "",
) -> MeetingRecording:
    """Transition de statut sécurisée : ne sort jamais d'un statut terminal."""
    if recording.is_terminal and status != recording.status:
        return recording  # idempotent : on n'écrase pas COMPLETED/FAILED
    recording.status = status
    if status == RecordingStatus.FAILED and error:
        recording.error_message = error[:2000]
        recording.processing_finished_at = timezone.now()
    if status == RecordingStatus.PROCESSING and not recording.processing_started_at:
        recording.processing_started_at = timezone.now()
    if status == RecordingStatus.COMPLETED:
        recording.processing_finished_at = timezone.now()
    recording.save(update_fields=[
        "status", "error_message", "processing_started_at",
        "processing_finished_at", "updated_at",
    ])
    return recording


def mark_uploaded(
    recording: MeetingRecording, *, file_obj, mime_type: str = "",
    original_filename: str = "", duration_seconds: Optional[float] = None,
) -> MeetingRecording:
    """Attache le fichier audio uploadé et passe en UPLOADED.

    Le fichier est stocké sur le backend STORAGES default (S3/MinIO en prod).
    Le caller (view) est responsable de valider le type MIME.
    """
    recording.audio_file = file_obj
    recording.original_filename = original_filename or getattr(file_obj, "name", "")[:300]
    recording.mime_type = mime_type[:80]
    recording.file_size = getattr(file_obj, "size", 0) or 0
    if duration_seconds is not None:
        recording.duration_seconds = float(duration_seconds)
    recording.uploaded_at = timezone.now()
    recording.stopped_at = recording.stopped_at or timezone.now()
    recording.status = RecordingStatus.UPLOADED
    recording.save()
    return recording


def mark_failed(recording: MeetingRecording, error: str) -> MeetingRecording:
    """Marque un enregistrement comme failed avec message d'erreur."""
    return update_status(recording, RecordingStatus.FAILED, error=error)
