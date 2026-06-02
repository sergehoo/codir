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

    Stratégie de stockage :
    1. Tente le storage par défaut (S3/MinIO en prod via django-storages).
    2. Si ça plante (clés manquantes, réseau, bucket inexistant), on log
       l'erreur et on FALLBACK sur un FileSystemStorage local (MEDIA_ROOT).
       Pratique en dev/CI/déploiement initial où S3 n'est pas encore configuré.
    3. Le caller est responsable du try/except au niveau view pour remonter
       proprement au front si même le fallback échoue.

    Le caller (view) est responsable de valider le type MIME en amont.
    """
    import logging
    from django.conf import settings
    from django.core.files.storage import FileSystemStorage

    log = logging.getLogger(__name__)

    # Métadonnées d'abord (gratuit, pas de risque I/O)
    recording.original_filename = original_filename or getattr(file_obj, "name", "")[:300]
    recording.mime_type = mime_type[:80]
    recording.file_size = getattr(file_obj, "size", 0) or 0
    if duration_seconds is not None:
        recording.duration_seconds = float(duration_seconds)

    # Tentative save fichier — on isole pour pouvoir fallback
    try:
        recording.audio_file = file_obj
        recording.save()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "mark_uploaded: storage par défaut KO (%s: %s). Fallback FileSystem.",
            type(exc).__name__, exc,
        )
        # Fallback : on force un FileSystemStorage local pour CETTE écriture.
        # On utilise MEDIA_ROOT (créé si absent) — pas idéal en prod, mais
        # permet de ne pas perdre l'audio quand S3 est en panne.
        media_root = getattr(settings, "MEDIA_ROOT", None) or "/var/www/media"
        try:
            import os
            os.makedirs(media_root, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass

        fs_storage = FileSystemStorage(location=media_root)
        # On bypass le storage par défaut en sauvegardant directement via
        # FileSystemStorage, puis on assigne le nom au FileField.
        try:
            fname = recording.audio_file.field.upload_to(recording, original_filename or "recording.audio")
            saved_name = fs_storage.save(fname, file_obj)
            # On stocke juste le nom (chemin relatif au MEDIA_ROOT)
            recording.audio_file.name = saved_name
        except Exception as fallback_exc:  # noqa: BLE001
            log.exception("mark_uploaded: fallback FileSystem KO également")
            # Re-raise pour que la view remonte un 502 explicite.
            raise

    recording.uploaded_at = timezone.now()
    recording.stopped_at = recording.stopped_at or timezone.now()
    recording.status = RecordingStatus.UPLOADED
    recording.save(update_fields=[
        "audio_file", "original_filename", "mime_type", "file_size",
        "duration_seconds", "uploaded_at", "stopped_at", "status", "updated_at",
    ])
    return recording


def mark_failed(recording: MeetingRecording, error: str) -> MeetingRecording:
    """Marque un enregistrement comme failed avec message d'erreur."""
    return update_status(recording, RecordingStatus.FAILED, error=error)
