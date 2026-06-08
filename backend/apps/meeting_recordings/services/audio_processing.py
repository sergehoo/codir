"""AudioProcessingService — extraction d'extraits speakers + normalisation.

Dépendances :
- pydub (Python) qui dépend de ffmpeg installé sur l'image Docker.
- Pour la bêta, on ne normalise PAS systématiquement (AssemblyAI accepte
  webm/ogg/mp3/wav directement). La normalisation est utilisée uniquement
  pour générer les extraits audio par speaker (5-8 sec).
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def _pydub_available() -> bool:
    try:
        import pydub  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def compress_for_transcription(src_path: str) -> Optional[str]:
    """Convertit l'audio source en Opus mono 16kHz 24kbps (optimisé voix).

    Gain typique :
      - 1h30 webm 256 kbps stéréo (≈150 Mo) → Opus 16kHz 24kbps mono (≈16 Mo)
      - Upload AAI 5× plus rapide + AAI traite plus vite l'input léger
      - Qualité de transcription/diarisation identique (la voix utilise <8kHz)

    Stratégie :
      - On utilise ffmpeg en subprocess (plus rapide et stable que pydub pour
        du transcodage massif). pydub est utilisé ailleurs pour les samples
        speakers où on a besoin d'API Python.
      - Si ffmpeg n'est pas installé, on retourne None et le caller utilise
        l'audio source non compressé (fallback gracieux).

    Retourne le path d'un fichier .ogg temp ou None si échec.
    Le caller est responsable du cleanup (os.unlink).
    """
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg introuvable — pas de compression pre-AAI.")
        return None

    if not os.path.exists(src_path):
        logger.warning("compress_for_transcription : src introuvable %s", src_path)
        return None

    src_size = os.path.getsize(src_path)

    # Sortie .ogg (container Ogg/Opus) — AAI le supporte nativement
    with tempfile.NamedTemporaryFile(
        suffix=".ogg", delete=False, prefix="aai_opus_",
    ) as dst:
        dst_path = dst.name

    # ffmpeg : -ac 1 = mono, -ar 16000 = 16kHz, libopus 24kbps optimisé voice
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", src_path,
        "-vn",                  # ignore vidéo (cas webm avec piste vidéo)
        "-c:a", "libopus",
        "-application", "voip", # mode voix : meilleur tradeoff voix/débit
        "-b:a", "24k",
        "-ac", "1",
        "-ar", "16000",
        dst_path,
    ]
    try:
        logger.info("compress_for_transcription : start (%.1f Mo source)", src_size / 1024 / 1024)
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            logger.warning(
                "ffmpeg compress KO (rc=%s): %s",
                proc.returncode, (proc.stderr or "")[:500],
            )
            try:
                os.unlink(dst_path)
            except Exception:  # noqa: BLE001
                pass
            return None
        dst_size = os.path.getsize(dst_path)
        ratio = (src_size / dst_size) if dst_size else 0
        logger.info(
            "compress_for_transcription : OK (%.1f Mo → %.1f Mo, gain %.1f×)",
            src_size / 1024 / 1024, dst_size / 1024 / 1024, ratio,
        )
        return dst_path
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg compress timeout (>10 min) — fallback source.")
        try:
            os.unlink(dst_path)
        except Exception:  # noqa: BLE001
            pass
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("ffmpeg compress crash: %s", exc)
        try:
            os.unlink(dst_path)
        except Exception:  # noqa: BLE001
            pass
        return None


def get_audio_duration(file_path_or_obj) -> float:
    """Retourne la durée en secondes via pydub. 0 si erreur (best-effort)."""
    if not _pydub_available():
        return 0.0
    try:
        from pydub import AudioSegment
        if hasattr(file_path_or_obj, "read"):
            audio = AudioSegment.from_file(file_path_or_obj)
        else:
            audio = AudioSegment.from_file(file_path_or_obj)
        return audio.duration_seconds
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_audio_duration failed: %s", exc)
        return 0.0


def normalize_audio(recording) -> Optional[bytes]:
    """Convertit l'audio source en WAV mono 16kHz et retourne les octets.

    Utilisé pour les extraits speakers (pydub aime le WAV). Pas stocké dans
    une FileField systématiquement (on l'utilise en mémoire pour découper).

    Retourne None si pydub indisponible (la bêta tolère cette absence —
    l'extrait audio par speaker est alors généré directement dans le format
    source via slicing approximatif).
    """
    if not _pydub_available():
        return None
    if not recording.audio_file:
        return None
    try:
        from pydub import AudioSegment
        # Lecture stream-friendly : on récupère le contenu et on passe à pydub.
        recording.audio_file.open("rb")
        try:
            data = recording.audio_file.read()
        finally:
            recording.audio_file.close()
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as src:
            src.write(data)
            src_path = src.name
        try:
            audio = AudioSegment.from_file(src_path)
            audio = audio.set_channels(1).set_frame_rate(16000)
            buf = io.BytesIO()
            audio.export(buf, format="wav")
            return buf.getvalue()
        finally:
            os.unlink(src_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("normalize_audio failed: %s", exc)
        return None


def extract_speaker_sample(
    recording, *, speaker_label: str, segments,
    target_duration_sec: Optional[float] = None,
) -> Optional[ContentFile]:
    """Génère un extrait audio représentatif pour un speaker.

    Stratégie :
    - Concatène les segments les plus longs du speaker jusqu'à atteindre
      ~target_duration_sec (défaut : settings.SPEAKER_SAMPLE_DURATION_SEC).
    - Exporte en MP3 (compact + supporté HTML5 audio universellement).
    - Retourne un ContentFile prêt à `instance.sample_audio.save(...)`.

    `segments` = queryset/list de SpeakerSegment pour ce speaker.
    """
    if not _pydub_available():
        logger.warning("extract_speaker_sample(%s) : pydub indisponible", speaker_label)
        return None
    if not recording.audio_file:
        logger.warning("extract_speaker_sample(%s) : pas d'audio source", speaker_label)
        return None
    target = target_duration_sec or getattr(
        settings, "SPEAKER_SAMPLE_DURATION_SEC", 8,
    )

    logger.info(
        "extract_speaker_sample(%s) : %d segments, target %ds",
        speaker_label, len(list(segments) if not isinstance(segments, list) else segments),
        target,
    )

    # Tri descendant par durée pour piquer les segments les plus parlés
    sorted_segs = sorted(
        segments,
        key=lambda s: (s.end_time - s.start_time),
        reverse=True,
    )

    try:
        from pydub import AudioSegment
        # Charge l'audio complet en mémoire (1× par recording, pas par speaker —
        # on délègue le caching au caller si besoin).
        recording.audio_file.open("rb")
        try:
            data = recording.audio_file.read()
        finally:
            recording.audio_file.close()
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as src:
            src.write(data)
            src_path = src.name
        try:
            full = AudioSegment.from_file(src_path)
            chunks: list = []
            accumulated_ms = 0
            target_ms = int(target * 1000)
            for seg in sorted_segs:
                if accumulated_ms >= target_ms:
                    break
                start_ms = max(0, int(seg.start_time * 1000))
                end_ms = min(len(full), int(seg.end_time * 1000))
                if end_ms <= start_ms:
                    continue
                # Tronque le segment si trop long pour ne pas dépasser le target
                slice_len = end_ms - start_ms
                remaining = target_ms - accumulated_ms
                if slice_len > remaining:
                    end_ms = start_ms + remaining
                chunks.append(full[start_ms:end_ms])
                accumulated_ms += (end_ms - start_ms)
            if not chunks:
                # Audio trop court ou pas de segments → fallback : extraire les
                # N premières secondes de l'audio complet (le speaker doit
                # probablement parler dedans).
                logger.info(
                    "extract_speaker_sample(%s) : pas de segments utilisables, "
                    "fallback sur les %ds initiaux de l'audio source",
                    speaker_label, min(target, len(full) // 1000),
                )
                fallback_end = min(len(full), target_ms or 8000)
                if fallback_end <= 0:
                    return None
                chunks = [full[:fallback_end]]
            # Concatène avec un fade-in/out léger entre les morceaux
            sample = chunks[0]
            for c in chunks[1:]:
                # crossfade ne marche que si chaque chunk >= 80ms
                try:
                    sample = sample.append(c, crossfade=min(80, len(c) // 2, len(sample) // 2))
                except Exception:  # noqa: BLE001
                    sample = sample + c   # concat sans crossfade
            sample = sample.set_channels(1).set_frame_rate(22050)
            buf = io.BytesIO()
            # MP3 garantit la lecture inline dans tous les navigateurs.
            sample.export(buf, format="mp3", bitrate="64k")
            output = ContentFile(buf.getvalue(),
                               name=f"sample_{speaker_label}.mp3")
            logger.info(
                "extract_speaker_sample(%s) : OK (%d Ko, %dms)",
                speaker_label, len(buf.getvalue()) // 1024, len(sample),
            )
            return output
        finally:
            os.unlink(src_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("extract_speaker_sample(%s) failed: %s", speaker_label, exc)
        return None
