"""Tâches Celery — pipeline async d'un enregistrement de réunion.

Orchestration :
    process_recording_task
        ├─ transcribe_recording_task
        ├─ diarize_recording_task
        ├─ extract_speaker_samples_task
        └─ (status → waiting_speaker_mapping ; attend l'utilisateur)

Après mapping manuel :
    generate_final_transcript_task
        └─ summarize_recording_task
                ├─ extract_decisions_task
                └─ extract_action_items_task
                        └─ status COMPLETED + notification

Retry : décorateur Celery autoretry_for sur exceptions transitoires.
Idempotence : chaque service appelé est conçu pour pouvoir être rejoué.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import (
    AIExtractionStatus, AIExtractionType,
    MeetingRecording, RecordingStatus,
)
from .services import (
    aggregate_speakers_from_segments,
    extract_action_items, extract_decisions, generate_final_transcript,
    generate_summary, suggest_participants_for_speakers,
    transcribe_recording, update_status,
)

logger = logging.getLogger(__name__)


# ─── Utilitaires ──────────────────────────────────────────────

def _get(rec_id: str) -> MeetingRecording | None:
    return MeetingRecording.unscoped.filter(id=rec_id).first()


def _fail(rec: MeetingRecording, msg: str):
    """Helper : marque l'enregistrement en FAILED et notifie."""
    update_status(rec, RecordingStatus.FAILED, error=msg)
    try:
        notify_recording_completed_task.delay(str(rec.id), failed=True)
    except Exception:  # noqa: BLE001
        pass


# ─── Pipeline ────────────────────────────────────────────────

@shared_task(
    bind=True, max_retries=2, default_retry_delay=30,
    autoretry_for=(IOError, OSError), retry_backoff=True,
)
def process_recording_task(self, recording_id: str):
    """Point d'entrée du pipeline : enchaîne transcription + diarisation + samples."""
    rec = _get(recording_id)
    if rec is None or rec.is_terminal:
        return "skipped"

    if rec.status not in (RecordingStatus.UPLOADED, RecordingStatus.PROCESSING):
        # On accepte aussi RECORDING / UPLOADING uniquement si déjà attaché.
        if not rec.audio_file:
            _fail(rec, "Pas de fichier audio attaché — process annulé.")
            return "no-audio"

    update_status(rec, RecordingStatus.PROCESSING)

    # 1. Transcription (synchrone Celery — bloque ce worker pendant l'appel AAI)
    update_status(rec, RecordingStatus.TRANSCRIBING)
    if not transcribe_recording(rec):
        _fail(rec, "Échec transcription AssemblyAI.")
        return "failed"

    # 2. Diarisation = simple agrégation des segments AAI déjà annotés
    update_status(rec, RecordingStatus.DIARIZING)
    aggregate_speakers_from_segments(rec)
    suggest_participants_for_speakers(rec)

    # 3. État WAITING_SPEAKER_MAPPING : l'utilisateur prend le relais.
    update_status(rec, RecordingStatus.WAITING_SPEAKER_MAPPING)

    try:
        notify_speaker_mapping_required_task.delay(str(rec.id))
    except Exception:  # noqa: BLE001
        pass
    return "waiting_mapping"


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def transcribe_recording_task(self, recording_id: str):
    """Lancé manuellement (debug/replay). Le flux normal passe par process."""
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    update_status(rec, RecordingStatus.TRANSCRIBING)
    return "ok" if transcribe_recording(rec) else "failed"


@shared_task(bind=True)
def diarize_recording_task(self, recording_id: str):
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    update_status(rec, RecordingStatus.DIARIZING)
    aggregate_speakers_from_segments(rec)
    suggest_participants_for_speakers(rec)
    update_status(rec, RecordingStatus.WAITING_SPEAKER_MAPPING)
    return "ok"


@shared_task(bind=True)
def extract_speaker_samples_task(self, recording_id: str):
    """Re-génère les extraits audio si pydub était indisponible lors du process initial."""
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    aggregate_speakers_from_segments(rec)  # re-run idempotent
    return "ok"


@shared_task(bind=True)
def generate_final_transcript_task(self, recording_id: str):
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    update_status(rec, RecordingStatus.GENERATING_FINAL_TRANSCRIPT)
    generate_final_transcript(rec)
    return "ok"


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def summarize_recording_task(self, recording_id: str):
    """Génère le résumé puis chaîne les extractions décisions/actions."""
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    update_status(rec, RecordingStatus.SUMMARIZING)
    text = generate_summary(rec)
    if not text:
        _fail(rec, "LLM résumé indisponible (Claude + DeepSeek KO).")
        return "failed"

    # Chaîne extraction décisions + actions
    update_status(rec, RecordingStatus.EXTRACTING_ACTIONS)
    extract_decisions(rec)
    extract_action_items(rec)
    update_status(rec, RecordingStatus.COMPLETED)
    try:
        notify_recording_completed_task.delay(str(rec.id))
    except Exception:  # noqa: BLE001
        pass
    return "ok"


@shared_task
def extract_decisions_task(recording_id: str):
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    extract_decisions(rec)
    return "ok"


@shared_task
def extract_action_items_task(recording_id: str):
    rec = _get(recording_id)
    if rec is None:
        return "missing"
    extract_action_items(rec)
    return "ok"


# ─── Maintenance ─────────────────────────────────────────────

@shared_task
def cleanup_failed_recordings_task():
    """Purge les enregistrements en FAILED depuis > 30 jours."""
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    qs = MeetingRecording.unscoped.filter(
        status=RecordingStatus.FAILED, updated_at__lt=cutoff,
    )
    count = qs.count()
    qs.delete()
    return count


# ─── Notifications utilisateur ────────────────────────────────

@shared_task
def notify_speaker_mapping_required_task(recording_id: str):
    """Notifie l'auteur de l'enregistrement que le mapping voix est requis."""
    rec = _get(recording_id)
    if rec is None or rec.recorded_by is None:
        return "skipped"
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import NotificationEvent
    except Exception:  # noqa: BLE001
        return "no-notif-module"
    try:
        notify(
            organization=rec.organization,
            recipient=rec.recorded_by,
            event=NotificationEvent.MEETING_COMPLETED,  # event générique réunion
            channel="internal",
            title=f"Voix à identifier : {rec.meeting.title}",
            body=("Votre enregistrement a été transcrit. "
                  "Vous pouvez maintenant identifier les voix détectées pour générer "
                  "le compte rendu final."),
            target=rec,
            link_url=f"/meetings/{rec.meeting_id}/recordings/{rec.id}/speakers",
            action_url=f"/meetings/{rec.meeting_id}/recordings/{rec.id}/speakers",
            send_email=False,
            priority="normal",
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify speaker mapping KO")
    return "ok"


@shared_task
def notify_recording_completed_task(recording_id: str, failed: bool = False):
    """Notifie l'auteur que le pipeline est terminé (ou en échec)."""
    rec = _get(recording_id)
    if rec is None or rec.recorded_by is None:
        return "skipped"
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import NotificationEvent
    except Exception:  # noqa: BLE001
        return "no-notif-module"

    if failed:
        title = f"Échec traitement audio : {rec.meeting.title}"
        body = (f"Le traitement de l'enregistrement a échoué. "
                f"Erreur : {rec.error_message or 'voir logs'}.")
        level = "danger"
    else:
        title = f"CR généré : {rec.meeting.title}"
        body = ("Votre compte rendu IA est prêt. Vous pouvez le relire, "
                "ajuster les décisions et les actions proposées avant de les créer.")
        level = "success"
    try:
        notify(
            organization=rec.organization,
            recipient=rec.recorded_by,
            event=NotificationEvent.MEETING_COMPLETED,
            channel="email",
            title=title, body=body, level=level,
            target=rec,
            link_url=f"/meetings/{rec.meeting_id}/recordings/{rec.id}/summary",
            action_url=f"/meetings/{rec.meeting_id}/recordings/{rec.id}/summary",
            send_email=True,
            priority="high" if failed else "normal",
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify recording completed KO")
    return "ok"
