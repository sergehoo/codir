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


def _extract_sample_ffmpeg(
    src_path: str, *, slices: list[tuple[float, float]],
) -> Optional[bytes]:
    """Extrait + concatène des slices d'audio via ffmpeg en streaming.

    Contrairement à pydub, ffmpeg :
      - ne charge PAS le fichier complet en RAM (streaming par démux)
      - utilise -ss / -t pour seek-then-extract (O(log n) au lieu de O(n))
      - encode directement en mp3 64kbps mono → output ~50-80 Ko

    Pour 1h30 d'audio source 150 Mo, l'extraction passe de ~30s + 1.5 Go RAM
    (pydub) à ~2s + 50 Mo RAM (ffmpeg). C'est essentiel pour ne pas OOM-killer
    le worker Celery sur les CODIR longs.

    `slices` = liste de (start_sec, end_sec) — on les concatène dans l'ordre.
    Retourne les bytes MP3 ou None si échec.
    """
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        return None
    if not slices:
        return None

    # Build le filter_complex qui découpe + concatène les slices.
    # Ex: [0:a]atrim=start=12.3:end=15.0,asetpts=PTS-STARTPTS[a0];
    #     [0:a]atrim=start=42:end=48,asetpts=PTS-STARTPTS[a1];
    #     [a0][a1]concat=n=2:v=0:a=1[out]
    parts: list[str] = []
    labels: list[str] = []
    for i, (s, e) in enumerate(slices):
        if e <= s:
            continue
        label = f"a{i}"
        labels.append(f"[{label}]")
        parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[{label}]")
    if not parts:
        return None
    n = len(labels)
    filter_complex = ";".join(parts) + f";{''.join(labels)}concat=n={n}:v=0:a=1[out]"

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, prefix="sample_") as dst:
        dst_path = dst.name
    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", src_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-ar", "22050",
            dst_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            logger.warning("ffmpeg sample extract KO: %s", (proc.stderr or "")[:300])
            return None
        with open(dst_path, "rb") as f:
            return f.read()
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg sample extract timeout")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffmpeg sample extract crash: %s", exc)
        return None
    finally:
        try:
            os.unlink(dst_path)
        except Exception:  # noqa: BLE001
            pass


def extract_speaker_sample(
    recording, *, speaker_label: str, segments,
    target_duration_sec: Optional[float] = None,
) -> Optional[ContentFile]:
    """Génère un extrait audio représentatif pour un speaker.

    Stratégie en cascade :
      1. ffmpeg subprocess (rapide, faible RAM) — préféré
      2. pydub (lent, charge tout en RAM) — fallback si ffmpeg absent,
         et seulement si la durée totale audio est raisonnable (<30 min).

    Pour 1h30+ d'audio, pydub chargeait 1.5+ Go de PCM en mémoire → OOM-kill
    silencieux du worker → pipeline bloqué en "diarizing". ffmpeg règle ça.

    `segments` = queryset/list de SpeakerSegment pour ce speaker.
    """
    if not recording.audio_file:
        logger.warning("extract_speaker_sample(%s) : pas d'audio source", speaker_label)
        return None
    target = target_duration_sec or getattr(
        settings, "SPEAKER_SAMPLE_DURATION_SEC", 8,
    )

    segs_list = list(segments) if not isinstance(segments, list) else segments
    logger.info(
        "extract_speaker_sample(%s) : %d segments, target %ds",
        speaker_label, len(segs_list), target,
    )

    # Tri descendant par durée pour piquer les segments les plus parlés
    sorted_segs = sorted(
        segs_list,
        key=lambda s: (s.end_time - s.start_time),
        reverse=True,
    )

    # Sélectionne les slices jusqu'à atteindre la durée cible
    selected: list[tuple[float, float]] = []
    accumulated = 0.0
    for seg in sorted_segs:
        if accumulated >= target:
            break
        s = max(0.0, float(seg.start_time))
        e = float(seg.end_time)
        if e <= s:
            continue
        slice_len = e - s
        remaining = target - accumulated
        if slice_len > remaining:
            e = s + remaining
        selected.append((s, e))
        accumulated += (e - s)

    # ── Tentative 1 : ffmpeg streaming (recommandé pour longs audios) ──
    import shutil as _sh
    if _sh.which("ffmpeg"):
        # On télécharge l'audio depuis le storage en local pour donner un path
        # à ffmpeg (storage = MinIO/S3, ffmpeg sait pas lire depuis Django).
        # Cette descente n'est faite QU'UNE FOIS par recording (pas par speaker)
        # → caller peut potentiellement caser le path entre speakers.
        src_path: Optional[str] = None
        try:
            recording.audio_file.open("rb")
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".audio", delete=False, prefix="src_sample_",
                ) as src:
                    while True:
                        block = recording.audio_file.read(1024 * 1024)
                        if not block:
                            break
                        src.write(block)
                    src_path = src.name
            finally:
                recording.audio_file.close()

            # Si aucun slice utilisable, fallback sur les N premières secondes
            if not selected:
                logger.info(
                    "extract_speaker_sample(%s) : fallback sur les %ds initiaux",
                    speaker_label, target,
                )
                selected = [(0.0, float(target))]

            mp3_bytes = _extract_sample_ffmpeg(src_path, slices=selected)
            if mp3_bytes:
                logger.info(
                    "extract_speaker_sample(%s) : OK via ffmpeg (%d Ko, %d slices)",
                    speaker_label, len(mp3_bytes) // 1024, len(selected),
                )
                return ContentFile(mp3_bytes, name=f"sample_{speaker_label}.mp3")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "extract_speaker_sample(%s) ffmpeg KO : %s — fallback pydub",
                speaker_label, exc,
            )
        finally:
            if src_path and os.path.exists(src_path):
                try:
                    os.unlink(src_path)
                except Exception:  # noqa: BLE001
                    pass

    # ── Tentative 2 : pydub (fallback, mais avec garde-fou taille) ──
    if not _pydub_available():
        logger.warning(
            "extract_speaker_sample(%s) : ni ffmpeg ni pydub disponibles",
            speaker_label,
        )
        return None

    # Garde-fou : pydub charge TOUT l'audio en RAM. Sur des fichiers > 30 min,
    # ça consomme plusieurs Go et risque l'OOM-kill. On refuse en mode dégradé
    # plutôt que de planter silencieusement.
    duration_total = float(recording.duration_seconds or 0)
    if duration_total > 30 * 60:
        logger.warning(
            "extract_speaker_sample(%s) : audio %ds > 30 min ET ffmpeg KO. "
            "On skip pour éviter OOM. Installe ffmpeg sur le worker.",
            speaker_label, int(duration_total),
        )
        return None

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
