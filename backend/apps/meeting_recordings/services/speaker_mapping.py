"""SpeakerMappingService — associe une voix à un participant, génère le transcript final."""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from ..models import (
    DetectedSpeaker, MeetingRecording, RecordingStatus,
    SpeakerParticipantMapping,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def map_speaker_to_participant(
    *, recording: MeetingRecording, speaker_label: str,
    participant, confirmed_by, notes: str = "",
) -> DetectedSpeaker:
    """Mappe une voix (SPEAKER_XX) à un User. Idempotent.

    - Met à jour le DetectedSpeaker correspondant (mapped_participant, display_name).
    - Crée une ligne SpeakerParticipantMapping (audit historique).
    - Ne marque PAS automatiquement is_confirmed=True ici : on attend
      `confirm_all_mappings()` pour passer la réunion au stade suivant.
    """
    sp = (
        DetectedSpeaker.unscoped
        .filter(recording=recording, speaker_label=speaker_label)
        .first()
    )
    if sp is None:
        raise ValueError(f"Speaker {speaker_label} inconnu pour ce recording.")

    display = " ".join(filter(None, [participant.first_name, participant.last_name])) \
              or participant.email
    sp.mapped_participant = participant
    sp.display_name = display[:200]
    sp.save(update_fields=["mapped_participant", "display_name", "updated_at"])

    SpeakerParticipantMapping.unscoped.create(
        organization=recording.organization,
        recording=recording,
        speaker_label=speaker_label,
        participant=participant,
        confirmed_by=confirmed_by,
        notes=notes[:300],
    )
    return sp


@transaction.atomic
def confirm_all_mappings(
    *, recording: MeetingRecording, confirmed_by,
) -> MeetingRecording:
    """Marque tous les DetectedSpeaker comme is_confirmed.

    Pré-requis : tous les speakers ont mapped_participant != null.
    Sinon ValueError (le caller doit afficher quels speakers manquent).
    """
    missing = list(
        DetectedSpeaker.unscoped
        .filter(recording=recording, mapped_participant__isnull=True)
        .values_list("speaker_label", flat=True)
    )
    if missing:
        raise ValueError(
            f"Speakers non mappés : {', '.join(missing)}",
        )
    DetectedSpeaker.unscoped.filter(recording=recording).update(
        is_confirmed=True, updated_at=timezone.now(),
    )
    return recording


def generate_final_transcript(recording: MeetingRecording) -> list[dict]:
    """Reconstruit transcript_final en remplaçant SPEAKER_XX par display_name.

    Met à jour `recording.transcript_final` (JSONField : liste de segments).
    Retourne la liste générée.
    """
    speakers = {
        s.speaker_label: (s.display_name or s.speaker_label)
        for s in DetectedSpeaker.unscoped.filter(recording=recording)
    }
    final: list[dict] = []
    for seg in recording.transcript_with_speakers or []:
        label = seg.get("speaker", "")
        final.append({
            "speaker": speakers.get(label, label),
            "speaker_label": label,
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": seg.get("text", ""),
        })
    recording.transcript_final = final
    recording.save(update_fields=["transcript_final", "updated_at"])
    return final


def format_transcript_for_llm(recording: MeetingRecording, *, max_chars: int = 60000) -> str:
    """Convertit le transcript disponible en texte plain pour les prompts IA.

    Cascade de sources (du plus structuré au moins) :
      1. `transcript_final`            → "Nom display : phrase"   (après mapping user)
      2. `transcript_with_speakers`    → "SPEAKER_00 : phrase"    (AAI avec diarisation,
                                          avant mapping manuel)
      3. `transcript_raw`              → texte brut sans speakers (mode
                                          skip_speaker_detection — aucun mapping possible)

    Tronque proprement à `max_chars` (limite raisonnable Claude/DeepSeek).
    """
    # ── 1. Mapping final déjà fait
    segments = recording.transcript_final or []
    if not segments:
        # ── 2. Diarisation AAI sans mapping
        segments = recording.transcript_with_speakers or []

    if segments:
        lines: list[str] = []
        total = 0
        for seg in segments:
            text = (seg.get("text", "") or "").strip()
            if not text:
                continue
            speaker = seg.get("speaker", "?")
            line = f"{speaker} : {text}"
            if total + len(line) + 1 > max_chars:
                lines.append("[…transcription tronquée…]")
                break
            lines.append(line)
            total += len(line) + 1
        return "\n".join(lines)

    # ── 3. Fallback texte brut (mode skip_speaker_detection)
    raw = (recording.transcript_raw or "").strip()
    if not raw:
        return ""
    if len(raw) > max_chars:
        return raw[:max_chars] + "\n[…transcription tronquée…]"
    return raw
