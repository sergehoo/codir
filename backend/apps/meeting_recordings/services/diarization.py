"""DiarizationService — agrège les SpeakerSegment en DetectedSpeaker.

AssemblyAI fait déjà la diarisation : on en hérite. Ce service se contente
d'agréger les segments par speaker_label et de générer 1 ligne DetectedSpeaker
par voix unique (+ extrait audio représentatif via audio_processing).

Étape suivante : suggestion fuzzy d'un participant (sans valider). L'objectif
est uniquement d'aider l'utilisateur, jamais d'affirmer une identification.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from django.db import transaction

from ..models import DetectedSpeaker, MeetingRecording, SpeakerSegment
from .audio_processing import extract_speaker_sample

logger = logging.getLogger(__name__)


def aggregate_speakers_from_segments(recording: MeetingRecording) -> list[DetectedSpeaker]:
    """Pour chaque speaker_label unique : crée/met-à-jour un DetectedSpeaker.

    Génère aussi un extrait audio si pydub disponible.
    Idempotent : peut être re-joué.

    Fallback : si AssemblyAI n'a renvoyé aucun segment diarisé (audio trop court
    ou mono-locuteur sans diarisation activée), on crée UN seul speaker fictif
    SPEAKER_00 couvrant toute la durée de l'audio. Comme ça l'utilisateur peut
    quand même mapper son enregistrement à un participant.
    """
    segments = list(SpeakerSegment.unscoped.filter(recording=recording))
    grouped: dict[str, list[SpeakerSegment]] = defaultdict(list)
    for s in segments:
        grouped[s.speaker_label].append(s)

    # Reset des DetectedSpeaker existants pour re-créer proprement
    DetectedSpeaker.unscoped.filter(recording=recording).delete()
    out: list[DetectedSpeaker] = []

    # ── Fallback : pas de diarisation AAI (audio court / mono-locuteur) ──
    # On crée 1 speaker fictif avec un segment couvrant tout l'audio.
    if not grouped:
        logger.warning(
            "Pas de segments diarisés pour recording %s — "
            "création d'un speaker fallback SPEAKER_00 couvrant tout l'audio.",
            recording.id,
        )
        total = recording.duration_seconds or 0
        if total > 0:
            # On crée 1 segment "synthétique" couvrant tout l'audio.
            seg = SpeakerSegment.unscoped.create(
                organization=recording.organization,
                recording=recording,
                speaker_label="SPEAKER_00",
                start_time=0.0,
                end_time=total,
                text=(recording.transcript_raw or "")[:1000],
                confidence=1.0,
            )
            grouped["SPEAKER_00"] = [seg]
            # Met à jour transcript_with_speakers pour cohérence frontend
            recording.transcript_with_speakers = [{
                "speaker": "SPEAKER_00",
                "start": 0.0,
                "end": total,
                "text": recording.transcript_raw or "",
                "confidence": 1.0,
            }]
            recording.save(update_fields=["transcript_with_speakers", "updated_at"])

    for label, segs in sorted(grouped.items()):
        total_dur = sum((s.end_time - s.start_time) for s in segs)
        avg_conf = sum(s.confidence for s in segs) / max(len(segs), 1)
        ds = DetectedSpeaker(
            organization=recording.organization,
            recording=recording,
            speaker_label=label,
            total_segments=len(segs),
            total_duration=round(total_dur, 2),
            confidence=round(avg_conf, 3),
        )
        ds.save()

        # Extrait audio représentatif — on attrape toute exception pour
        # ne pas faire planter toute la diarisation si pydub a un souci sur
        # 1 speaker (les autres doivent pouvoir continuer).
        try:
            sample = extract_speaker_sample(
                recording, speaker_label=label, segments=segs,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "extract_speaker_sample a levé une exception pour %s : %s",
                label, exc,
            )
            sample = None

        if sample is not None:
            try:
                ds.sample_audio.save(sample.name, sample, save=True)
                logger.info(
                    "Sample audio sauvegardé pour %s : %s (%d bytes)",
                    label, ds.sample_audio.name, ds.sample_audio.size,
                )
            except Exception as exc:  # noqa: BLE001
                # Upload S3/MinIO a planté — on log clairement mais on continue
                # pour les autres speakers. L'utilisateur verra le speaker sans
                # extrait audio écoutable (mais avec stats correctes).
                logger.exception(
                    "Échec save() sample_audio pour %s : %s",
                    label, exc,
                )
                # On nettoie le name au cas où Django l'aurait setté avant le save final
                ds.sample_audio = None
                ds.save(update_fields=["sample_audio", "updated_at"])
        else:
            logger.warning(
                "Sample audio non généré pour %s (pydub retourne None)",
                label,
            )

        out.append(ds)
    return out


# ─── Suggestion fuzzy de participants ──────────────────────────────

def _name_matches(transcript: str, full_name: str) -> int:
    """Compte le nombre d'occurrences (approx) du nom dans le transcript."""
    if not transcript or not full_name:
        return 0
    text = transcript.lower()
    parts = [p for p in full_name.lower().split() if len(p) >= 3]
    return sum(text.count(p) for p in parts)


def suggest_participants_for_speakers(recording: MeetingRecording) -> None:
    """Pour chaque DetectedSpeaker, propose un participant probable.

    Heuristique très simple :
    - on tokenize le transcript_raw,
    - pour chaque participant officiel de la réunion, on compte le nombre
      de mentions de son nom dans la transcription,
    - on propose le participant avec le plus de mentions (>0).

    C'est une SUGGESTION non engageante (mapped_participant reste null).
    L'utilisateur a toujours le dernier mot.
    """
    text = recording.transcript_raw or ""
    if not text:
        return

    # Récupère les participants utilisateurs (pas les externals).
    # On passe par unscoped pour ne pas dépendre du contexte tenant courant
    # (Celery context).
    try:
        from apps.meetings.models import MeetingParticipant
    except Exception:  # noqa: BLE001
        return

    participants = list(
        MeetingParticipant.unscoped
        .filter(meeting=recording.meeting, user__isnull=False)
        .select_related("user")
    )
    if not participants:
        return

    # Pré-calcule des scores : { user_id: total_mentions }
    user_scores: dict = {}
    user_objs: dict = {}
    for p in participants:
        u = p.user
        if not u:
            continue
        full_name = " ".join(filter(None, [u.first_name, u.last_name])) or u.email
        score = _name_matches(text, full_name)
        if score > 0:
            user_scores[u.id] = score
            user_objs[u.id] = u

    if not user_scores:
        return

    # Trie speakers par durée parlée (plus on parle, plus on est probable
    # d'être l'orateur le plus mentionné = chair / présentateur).
    speakers = list(
        DetectedSpeaker.unscoped
        .filter(recording=recording)
        .order_by("-total_duration")
    )

    # Greedy assignment : assignment 1-1 (chaque utilisateur suggéré 1 fois max).
    used: set = set()
    for sp in speakers:
        # Cherche le user le plus mentionné qui n'a pas encore été pris.
        candidates = sorted(
            (uid for uid in user_scores if uid not in used),
            key=lambda uid: user_scores[uid],
            reverse=True,
        )
        if not candidates:
            break
        best = candidates[0]
        sp.suggested_participant = user_objs[best]
        sp.save(update_fields=["suggested_participant", "updated_at"])
        used.add(best)
