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
        # ─── Stratégie 2026 : ne PAS spécifier speech_model ─────
        # AssemblyAI a déprécié `speech_model="best"` (envoie 400 erreur).
        # Le nouveau format API est `speech_models=["universal-3-pro", ...]`
        # (pluriel + liste), mais tous les SDK Python ne sont pas alignés.
        # Solution résiliente : on ne passe AUCUN paramètre de modèle → le
        # serveur AssemblyAI utilise son meilleur défaut (universal-2 en 2026)
        # qui supporte le français nativement.
        #
        # Si tu veux forcer un modèle spécifique, définis ASSEMBLYAI_MODEL
        # dans .env.prod (ex: "universal-2", "slam-1") ET assure-toi que la
        # version du SDK assemblyai installée le supporte.
        config_kwargs = dict(
            language_code=getattr(settings, "ASSEMBLYAI_LANGUAGE", "fr"),
            speaker_labels=True,
            # Garde les mots exacts (CR exécutif) sans masquage profanité
            filter_profanity=False,
            # punctuate=True et format_text=True sont les défauts → texte lisible
        )

        model_name = getattr(settings, "ASSEMBLYAI_MODEL", "") or ""
        config = None
        if model_name:
            # Tentative 1 : avec speech_model si le user a explicitement forcé
            try:
                speech_model = getattr(aai.SpeechModel, model_name, model_name)
                config = aai.TranscriptionConfig(
                    speech_model=speech_model, **config_kwargs,
                )
            except (TypeError, AttributeError) as exc:
                logger.warning(
                    "speech_model=%s rejeté par le SDK (%s), fallback défaut.",
                    model_name, exc,
                )
                config = None

        if config is None:
            # Défaut serveur AssemblyAI = compatible 2026
            config = aai.TranscriptionConfig(**config_kwargs)

        transcriber = aai.Transcriber(config=config)
        logger.info(
            "AAI transcribe start: recording=%s model=%s lang=%s url=%s",
            recording.id, model_name or "(défaut serveur)",
            config_kwargs.get("language_code"),
            audio_input if isinstance(audio_input, str) else "(bytes uploadés)",
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
