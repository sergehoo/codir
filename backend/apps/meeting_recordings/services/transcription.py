"""TranscriptionService — wrapper AssemblyAI.

AssemblyAI fournit transcription + diarisation (speaker labels) en un seul
appel. Pour le français, on utilise `speech_model="best"` qui supporte
`speaker_labels=True`.

L'appel est synchrone côté backend Python mais s'exécute dans une Celery
task — la latence (~1× le temps audio en mode best) est donc isolée du
front et n'impacte pas l'UX. Le statut est rafraîchi régulièrement.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from django.conf import settings

from ..models import MeetingRecording, RecordingStatus, SpeakerSegment

logger = logging.getLogger(__name__)


def _build_aai_client():
    """Importe assemblyai en lazy + configure la clé API.

    Lazy pour ne pas planter l'app si la lib n'est pas installée (dev sans
    audio). Retourne None si la lib ou la clé manquent — caller doit gérer.
    """
    api_key = getattr(settings, "ASSEMBLYAI_API_KEY", "")
    if not api_key:
        logger.error("ASSEMBLYAI_API_KEY non configurée — transcription impossible.")
        return None
    try:
        import assemblyai as aai
    except ImportError:
        logger.exception("assemblyai non installé")
        return None
    aai.settings.api_key = api_key
    return aai


def transcribe_recording(recording: MeetingRecording) -> bool:
    """Envoie l'audio à AssemblyAI, attend le résultat, et hydrate :
    - recording.transcript_raw (texte brut)
    - recording.transcript_with_speakers (segments structurés)
    - SpeakerSegment (1 ligne par utterance).

    Retourne True si succès, False sinon (la task Celery se charge de retry).
    """
    aai = _build_aai_client()
    if aai is None:
        return False
    if not recording.audio_file:
        logger.error("recording %s : pas de fichier audio", recording.id)
        return False

    # Best-effort : URL présignée S3 si le storage le supporte, sinon upload direct.
    audio_input = _resolve_audio_url(recording)
    if audio_input is None:
        return False

    try:
        # ─── speech_model ─────────────────────────────────────
        # AssemblyAI a déprécié les anciens modèles "best" / "nano" en 2025.
        # Nouveaux modèles : "universal" (générique multilingue, défaut),
        # "slam-1" (anglais+français focus), "nano" (rapide bas coût).
        # On choisit le modèle via env pour pouvoir changer sans rebuild.
        # Si non défini, on laisse le défaut serveur → robuste aux changements futurs.
        model_name = getattr(settings, "ASSEMBLYAI_MODEL", "universal")
        # Essaie de mapper sur l'enum SDK si dispo ; sinon passe la string brute.
        try:
            speech_model = getattr(aai.SpeechModel, model_name, model_name)
        except Exception:  # noqa: BLE001
            speech_model = model_name

        config_kwargs = dict(
            language_code=getattr(settings, "ASSEMBLYAI_LANGUAGE", "fr"),
            speaker_labels=True,
            # Désactive le filtrage profanité (CR exécutif = on garde le mot exact)
            filter_profanity=False,
            # punctuate=True et format_text=True (défauts) : texte lisible.
        )
        if speech_model:
            config_kwargs["speech_model"] = speech_model

        try:
            config = aai.TranscriptionConfig(**config_kwargs)
        except TypeError as exc:
            # Compat SDK : si speech_model n'est plus un paramètre valide,
            # on retombe sur la config sans modèle (défaut serveur = universal).
            logger.warning("TranscriptionConfig sans speech_model: %s", exc)
            config_kwargs.pop("speech_model", None)
            config = aai.TranscriptionConfig(**config_kwargs)

        transcriber = aai.Transcriber(config=config)
        logger.info(
            "AAI transcribe start: recording=%s model=%s lang=%s",
            recording.id, speech_model, config_kwargs.get("language_code"),
        )
        transcript = transcriber.transcribe(audio_input)
        if transcript.status == aai.TranscriptStatus.error:
            err = (transcript.error or "Erreur AssemblyAI inconnue")[:1000]
            logger.error("AAI transcription error: %s", err)
            recording.error_message = err
            recording.save(update_fields=["error_message", "updated_at"])
            return False

        # Texte brut complet (utile pour le résumé fallback si pas d'utterances)
        recording.transcript_raw = transcript.text or ""
        # Hydrate segments
        _persist_utterances(recording, transcript)
        recording.save(update_fields=["transcript_raw",
                                      "transcript_with_speakers", "updated_at"])
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("transcribe_recording failed")
        recording.error_message = f"AAI: {exc}"[:2000]
        recording.save(update_fields=["error_message", "updated_at"])
        return False


def _resolve_audio_url(recording: MeetingRecording) -> Optional[str]:
    """Renvoie une URL accessible publiquement (présignée S3) ou un path local."""
    try:
        # Si le storage gère url() en présigné, AssemblyAI fetch directement.
        return recording.audio_file.url
    except Exception:  # noqa: BLE001
        logger.warning("storage.url() KO — fallback : upload via assemblyai SDK")
    # Fallback : on lit les octets et on laisse le SDK uploader vers AssemblyAI.
    try:
        recording.audio_file.open("rb")
        try:
            data = recording.audio_file.read()
        finally:
            recording.audio_file.close()
        # Le SDK assemblyai accepte un path local OU des bytes via Transcriber.transcribe().
        return data  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Impossible de lire l'audio: %s", exc)
        return None


def _persist_utterances(recording: MeetingRecording, transcript) -> None:
    """Convertit transcript.utterances (AssemblyAI) → SpeakerSegment + JSON."""
    utterances = getattr(transcript, "utterances", None) or []
    serialized: list = []
    # Wipe existing segments (idempotent rerun)
    SpeakerSegment.unscoped.filter(recording=recording).delete()
    bulk: list = []
    for u in utterances:
        seg_data = {
            "speaker": f"SPEAKER_{int(u.speaker):02d}" if str(u.speaker).isdigit()
                       else f"SPEAKER_{u.speaker}",
            # Les timestamps AAI sont en millisecondes
            "start": (u.start or 0) / 1000.0,
            "end": (u.end or 0) / 1000.0,
            "text": (u.text or "").strip(),
            "confidence": float(u.confidence or 0),
        }
        serialized.append(seg_data)
        bulk.append(SpeakerSegment(
            organization=recording.organization,
            recording=recording,
            speaker_label=seg_data["speaker"],
            start_time=seg_data["start"],
            end_time=seg_data["end"],
            text=seg_data["text"],
            confidence=seg_data["confidence"],
        ))
    if bulk:
        SpeakerSegment.unscoped.bulk_create(bulk, batch_size=200)
    recording.transcript_with_speakers = serialized
    # Met à jour duration_seconds si on ne l'avait pas
    if utterances and not recording.duration_seconds:
        recording.duration_seconds = max((u.end or 0) for u in utterances) / 1000.0
