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
        msg = "Client AssemblyAI indisponible (clé manquante ou lib non installée)."
        logger.error(msg)
        recording.error_message = msg
        recording.save(update_fields=["error_message", "updated_at"])
        return False
    if not recording.audio_file:
        msg = f"Pas de fichier audio attaché au recording {recording.id}"
        logger.error(msg)
        recording.error_message = msg
        recording.save(update_fields=["error_message", "updated_at"])
        return False

    # Télécharge l'audio depuis le storage en local — le SDK AAI uploadera
    # ensuite vers leur infra. Bypass propre de la dépendance MinIO public.
    audio_input = _download_audio_to_temp(recording)
    if audio_input is None:
        msg = "Impossible de télécharger l'audio depuis le storage local."
        logger.error(msg)
        recording.error_message = msg
        recording.save(update_fields=["error_message", "updated_at"])
        return False
    logger.info("Audio téléchargé localement : %s", audio_input)

    # ─── Pre-downsample Opus 24kbps — UNIQUEMENT si pas de diarisation ─────
    # ⚠ La diarisation AAI a besoin de :
    #   - stéréo (la spatialisation aide à séparer les voix)
    #   - fréquences > 8 kHz (timbres distincts)
    # Si on compresse en mono 16kHz, AAI ne distingue plus les voix → 1 seul
    # speaker détecté même pour un CODIR à 5 personnes. On ne compresse donc
    # QUE quand `skip_speaker_detection=True` (l'utilisateur ne veut pas la
    # diarisation et accepte le trade-off vitesse vs précision speakers).
    wants_speakers_for_compress = not bool(
        getattr(recording, "skip_speaker_detection", False)
    )
    if wants_speakers_for_compress:
        logger.info(
            "Pre-downsample skip : diarisation demandée (rec=%s). "
            "AAI reçoit l'audio source pour préserver la qualité voix.",
            recording.id,
        )
    else:
        # Mode rapide : compression sans diarisation → on peut aller en mono 16kHz
        from .audio_processing import compress_for_transcription
        compressed_path = compress_for_transcription(audio_input)
        if compressed_path:
            try:
                import os as _os
                _os.unlink(audio_input)
            except Exception:  # noqa: BLE001
                pass
            audio_input = compressed_path
            logger.info("AAI utilisera la version compressée : %s", audio_input)

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
        # ⚡ skip_speaker_detection : si activé, on demande à AAI de PAS faire
        # la diarisation. AAI traite alors l'audio ~2× plus vite (pas de
        # clustering speakers + pas d'utterances structurées). Le pipeline
        # Celery enchaîne ensuite directement transcript → résumé sans
        # passer par l'étape WAITING_SPEAKER_MAPPING.
        wants_speakers = not bool(getattr(recording, "skip_speaker_detection", False))
        config_kwargs = dict(
            language_code=getattr(settings, "ASSEMBLYAI_LANGUAGE", "fr"),
            speaker_labels=wants_speakers,
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
            "AAI transcribe start: recording=%s model=%s lang=%s local_path=%s",
            recording.id, model_name or "(défaut serveur)",
            config_kwargs.get("language_code"),
            audio_input,
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

        # Diagnostic : combien de speakers AAI a-t-il détectés ?
        # Si on a demandé speaker_labels=True mais qu'AAI renvoie 1 seul speaker
        # alors que la réunion en a clairement plusieurs, c'est un signal que :
        #   - L'audio est mono très compressé (la diarisation marche mieux en stéréo)
        #   - Les voix se ressemblent ou s'interrompent trop souvent
        #   - Le micro était unique (1 seul flux) et AAI ne distingue pas les locuteurs
        unique_speakers = set()
        for u in (getattr(transcript, "utterances", None) or []):
            unique_speakers.add(str(u.speaker))
        logger.info(
            "AAI transcribe DONE: rec=%s speakers_detected=%d (wanted=%s) utterances=%d text=%d chars",
            recording.id, len(unique_speakers), wants_speakers,
            len(getattr(transcript, "utterances", None) or []),
            len(recording.transcript_raw),
        )
        if wants_speakers and len(unique_speakers) <= 1:
            logger.warning(
                "AAI rec=%s : 1 seul speaker détecté malgré speaker_labels=True. "
                "Causes probables : audio mono ré-encodé (compress pre-AAI), "
                "voix similaires, ou enregistrement à 1 micro. "
                "L'utilisateur peut ré-uploader sans pré-compression ou utiliser le mode rapide.",
                recording.id,
            )

        recording.save(update_fields=["transcript_raw",
                                      "transcript_with_speakers", "updated_at"])
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("transcribe_recording failed")
        recording.error_message = f"AAI: {exc}"[:2000]
        recording.save(update_fields=["error_message", "updated_at"])
        return False
    finally:
        # Nettoyage systématique du fichier temp téléchargé (qu'on ait
        # réussi ou échoué). Crucial pour ne pas remplir /tmp sur des
        # workers qui traitent beaucoup d'audios.
        import os
        if isinstance(audio_input, str) and audio_input.startswith("/tmp/"):
            try:
                os.unlink(audio_input)
                logger.debug("Audio temp supprimé : %s", audio_input)
            except Exception:  # noqa: BLE001
                pass


def _download_audio_to_temp(recording: MeetingRecording) -> Optional[str]:
    """Télécharge l'audio depuis le storage (MinIO/S3) vers un fichier temp local.

    Stratégie volontaire : on NE PASSE PAS d'URL publique à AssemblyAI car :
    1. L'URL présignée MinIO requiert que `storage-codir.datarium-dev.com` soit
       accessible depuis Internet (DNS + certif TLS + Traefik OK) — fragile.
    2. Un download local + upload AAI direct fonctionne dans tous les cas, même
       si MinIO est en réseau privé.
    3. C'est aussi plus sécurisé : l'audio n'est jamais exposé publiquement.

    Le SDK `assemblyai` détecte un path local et upload le fichier sur leur
    storage interne avant de lancer la transcription.

    Retourne le path absolu du fichier temp. Caller DOIT cleaner via os.unlink().
    """
    import tempfile
    if not recording.audio_file:
        return None

    # Préserve l'extension (webm/mp3/ogg/...) — utile pour que AAI sniff le type.
    name = recording.audio_file.name or ""
    ext = ".webm"
    if "." in name:
        ext = "." + name.rsplit(".", 1)[1].lower()

    try:
        # Ouvre le fichier depuis le storage Django (S3 ou FileSystem).
        recording.audio_file.open("rb")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, prefix="aai_",
            ) as tmp:
                # Streaming par chunks pour ne pas exploser la RAM sur de longs audios.
                while True:
                    chunk = recording.audio_file.read(1024 * 1024)  # 1 Mo
                    if not chunk:
                        break
                    tmp.write(chunk)
                tmp_path = tmp.name
        finally:
            recording.audio_file.close()
        return tmp_path
    except Exception as exc:  # noqa: BLE001
        logger.exception("Téléchargement audio local KO: %s", exc)
        return None


# Alias rétrocompat : l'ancien nom est encore utilisé en cas d'imports externes.
_resolve_audio_url = _download_audio_to_temp


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
