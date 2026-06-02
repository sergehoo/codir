"""Signaux meeting_recordings — branchent l'audit log automatique.

La logique métier (transition de statut, notifications) reste dans
`services` + `tasks`. Ici on se contente de poser des traces d'audit
pour la conformité (qui a démarré quoi, quand, depuis quel IP).
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import (
    DetectedSpeaker, MeetingRecording, RecordingAIExtraction,
    SpeakerParticipantMapping,
)

logger = logging.getLogger(__name__)


def _audit(*, action: str, target, description: str = ""):
    """Wrapper résilient autour d'apps.audit_logs.services.log."""
    try:
        from apps.audit_logs.services import log as audit_log
        audit_log(action=action, target=target, description=description)
    except Exception:  # noqa: BLE001
        logger.warning("Audit log indisponible (ignoré).")


@receiver(post_save, sender=MeetingRecording)
def on_recording_saved(sender, instance: MeetingRecording, created, **kwargs):
    if created:
        _audit(
            action="created", target=instance,
            description=f"Enregistrement créé pour {instance.meeting.title}",
        )
    else:
        # On audit uniquement les transitions clés pour ne pas spammer.
        if instance.status in ("uploaded", "completed", "failed", "waiting_speaker_mapping"):
            _audit(
                action="status_changed", target=instance,
                description=f"Statut → {instance.status}",
            )


@receiver(post_delete, sender=MeetingRecording)
def on_recording_deleted(sender, instance: MeetingRecording, **kwargs):
    _audit(
        action="deleted", target=instance,
        description=f"Enregistrement supprimé ({instance.meeting_id})",
    )


@receiver(post_save, sender=SpeakerParticipantMapping)
def on_mapping_saved(sender, instance: SpeakerParticipantMapping, created, **kwargs):
    if created:
        _audit(
            action="created", target=instance,
            description=(f"Mapping voix {instance.speaker_label} → "
                         f"{instance.participant.email}"),
        )


@receiver(post_save, sender=RecordingAIExtraction)
def on_ai_extraction_saved(sender, instance: RecordingAIExtraction, created, **kwargs):
    if created:
        _audit(
            action="created", target=instance,
            description=f"Extraction IA {instance.extraction_type} (DRAFT)",
        )
    elif instance.status == "pushed":
        _audit(
            action="status_changed", target=instance,
            description=f"Extraction {instance.extraction_type} validée + poussée",
        )
