"""Chunked upload service — pour les enregistrements > 50 Mo.

Flux :
  1. `init_chunked_upload()` → crée un MeetingRecording vide en statut CREATED,
     calcule la taille de chunk et le nombre attendu.
  2. `save_chunk()` → persiste un RecordingChunk (sur le storage 'recordings'
     ou fallback FileSystem). Idempotent par (recording_id, chunk_index).
  3. `get_upload_status()` → liste les chunks déjà reçus, calcule la
     progression côté serveur (utile pour la reprise après coupure).
  4. `finalize_chunked_upload()` → assemble tous les chunks en `audio_file`
     final, met à jour les métadonnées, supprime les chunks intermédiaires,
     déclenche le pipeline Celery.

Conception :
  - On NE stocke jamais l'audio complet en RAM : on stream chunk par chunk
    lors de l'assemblage (lecture seq + écriture seq).
  - Les chunks sont sauvegardés dans le bucket `recordings` (déjà configuré).
  - Si MinIO/S3 est down, fallback FileSystem (cohérent avec mark_uploaded).
  - L'opération est partiellement résumable : si un chunk plante, le client
    peut consulter `/status/` puis renvoyer uniquement les chunks manquants.
"""
from __future__ import annotations

import hashlib
import logging
import os
from io import BytesIO
from typing import Optional

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone

from ..models import MeetingRecording, RecordingChunk, RecordingStatus
from .recording import update_status, mark_failed

log = logging.getLogger(__name__)

# Taille de chunk imposée côté serveur si le client ne la précise pas.
# 50 Mo : compromis entre nb requêtes et overhead par chunk.
DEFAULT_CHUNK_SIZE_BYTES = 50 * 1024 * 1024


def _max_upload_bytes() -> int:
    return getattr(settings, "MAX_RECORDING_UPLOAD_MB", 600) * 1024 * 1024


# ─── 1. Init ──────────────────────────────────────────────────

def init_chunked_upload(
    *, meeting, recorded_by,
    filename: str, total_size_bytes: int, content_type: str = "",
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
    title: str = "",
    duration_seconds: Optional[float] = None,
    consent_acknowledged: bool = False,
    skip_speaker_detection: bool = False,
) -> tuple[MeetingRecording, int, int]:
    """Crée le MeetingRecording cible et retourne (rec, chunk_size, total_chunks).

    Le client doit ensuite envoyer `total_chunks` PUT sur
    /recordings/upload/{recording_id}/chunks/{idx}/.
    """
    max_bytes = _max_upload_bytes()
    if total_size_bytes <= 0:
        raise ValueError("Taille du fichier requise (octets).")
    if total_size_bytes > max_bytes:
        raise ValueError(
            f"Fichier trop volumineux ({total_size_bytes / 1024 / 1024:.1f} Mo > "
            f"{max_bytes / 1024 / 1024:.0f} Mo). Augmentez MAX_RECORDING_UPLOAD_MB."
        )

    # Borne le chunk_size pour éviter abus (entre 1 Mo et 100 Mo).
    chunk_size = max(1 * 1024 * 1024, min(chunk_size_bytes, 100 * 1024 * 1024))
    total_chunks = (total_size_bytes + chunk_size - 1) // chunk_size  # ceil-div

    rec = MeetingRecording(
        organization=meeting.organization,
        meeting=meeting,
        recorded_by=recorded_by,
        title=title or f"Enregistrement {meeting.title}"[:250],
        status=RecordingStatus.UPLOADING,
        started_at=timezone.now(),
        original_filename=filename[:300],
        mime_type=content_type[:80],
        file_size=total_size_bytes,
        skip_speaker_detection=bool(skip_speaker_detection),
    )
    if consent_acknowledged:
        rec.consent_acknowledged_at = timezone.now()
    if duration_seconds is not None:
        rec.duration_seconds = float(duration_seconds)
    rec.save()

    log.info(
        "init_chunked: rec=%s file=%s size=%s chunks=%s (chunk_size=%s)",
        rec.id, filename, total_size_bytes, total_chunks, chunk_size,
    )
    return rec, chunk_size, total_chunks


# ─── 2. Save d'un chunk ───────────────────────────────────────

@transaction.atomic
def save_chunk(
    *, recording: MeetingRecording, chunk_index: int, chunk_file,
    expected_size: Optional[int] = None,
) -> RecordingChunk:
    """Persiste un chunk. Idempotent : si déjà présent, écrase (re-essai client)."""
    if chunk_index < 0:
        raise ValueError("chunk_index doit être >= 0")

    # Calcule sha256 en streaming pour vérification d'intégrité
    sha = hashlib.sha256()
    size = 0
    buffer = BytesIO()
    for piece in chunk_file.chunks(chunk_size=64 * 1024):
        sha.update(piece)
        size += len(piece)
        buffer.write(piece)
    buffer.seek(0)
    checksum = sha.hexdigest()

    if expected_size is not None and size != expected_size:
        log.warning(
            "save_chunk: taille KO rec=%s idx=%s got=%s expected=%s",
            recording.id, chunk_index, size, expected_size,
        )

    # Supprime l'ancien chunk s'il existe (idempotence pour retry)
    existing = RecordingChunk.unscoped.filter(
        recording=recording, index=chunk_index,
    ).first()
    if existing:
        try:
            existing.chunk_file.delete(save=False)
        except Exception:  # noqa: BLE001
            pass
        existing.delete()

    fname = f"chunk_{chunk_index:04d}.bin"
    file_obj = ContentFile(buffer.read(), name=fname)

    try:
        chunk = RecordingChunk(
            organization=recording.organization,
            recording=recording,
            index=chunk_index,
            size=size,
            checksum=checksum,
        )
        chunk.chunk_file = file_obj
        chunk.save()
    except Exception as exc:  # noqa: BLE001
        # Fallback FileSystem (cohérent avec mark_uploaded).
        log.warning(
            "save_chunk: storage par défaut KO (%s: %s). Fallback FileSystem.",
            type(exc).__name__, exc,
        )
        media_root = getattr(settings, "MEDIA_ROOT", None) or "/var/www/media"
        try:
            os.makedirs(media_root, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
        fs_storage = FileSystemStorage(location=media_root)
        rel_path = chunk.chunk_file.field.upload_to(chunk, fname)
        buffer.seek(0)
        saved_name = fs_storage.save(rel_path, file_obj)
        chunk.chunk_file.name = saved_name
        chunk.save()

    return chunk


# ─── 3. Status ────────────────────────────────────────────────

def get_upload_status(recording: MeetingRecording) -> dict:
    """Retourne l'état complet de l'upload chunked (pour reprise)."""
    chunks = list(
        RecordingChunk.unscoped
        .filter(recording=recording)
        .order_by("index")
        .values("index", "size", "checksum")
    )
    uploaded_indexes = [c["index"] for c in chunks]
    uploaded_bytes = sum(c["size"] for c in chunks)
    return {
        "recording_id": str(recording.id),
        "status": recording.status,
        "expected_total_bytes": recording.file_size,
        "uploaded_bytes": uploaded_bytes,
        "uploaded_chunks": uploaded_indexes,
        "uploaded_count": len(uploaded_indexes),
        "chunks": chunks,
    }


# ─── 4. Finalize : assemble + déclenche pipeline ──────────────

@transaction.atomic
def finalize_chunked_upload(
    *, recording: MeetingRecording, total_chunks: int,
) -> MeetingRecording:
    """Assemble les chunks en `audio_file` final, met à jour, déclenche Celery.

    Streaming : pas de chargement complet en RAM. On lit chaque chunk en
    séquence et on écrit dans un buffer disque temporaire, puis on sauvegarde
    via FileField (qui réuploade vers S3).
    """
    chunks = list(
        RecordingChunk.unscoped
        .filter(recording=recording)
        .order_by("index")
    )
    received_indexes = {c.index for c in chunks}
    missing = [i for i in range(total_chunks) if i not in received_indexes]
    if missing:
        raise ValueError(
            f"Chunks manquants pour assemblage : {missing[:10]} "
            f"({len(missing)} au total)"
        )

    # Concatène en streaming dans un fichier temporaire local (rapide).
    #
    # ⚠ On NE peut PAS utiliser /tmp par défaut : en prod le container a un
    # tmpfs de 128 Mo sur /tmp, un fichier reconstitué de 100+ Mo provoque
    # ENOSPC ("No space left on device") → 500 puis crash worker → 502.
    # On spool donc dans MEDIA_ROOT/chunked_uploads_tmp qui est sur un vrai
    # volume disque. Configurable via CHUNKED_UPLOAD_TEMP_DIR.
    import tempfile
    media_root = getattr(settings, "MEDIA_ROOT", None) or "/var/www/media"
    spool_dir = getattr(settings, "CHUNKED_UPLOAD_TEMP_DIR", None) or os.path.join(
        media_root, "chunked_uploads_tmp"
    )
    try:
        os.makedirs(spool_dir, exist_ok=True)
    except OSError as _mk_exc:
        log.warning(
            "finalize: impossible de créer spool_dir=%s (%s), fallback sur tempfile default",
            spool_dir, _mk_exc,
        )
        spool_dir = None  # → tempfile utilisera le default système

    tmp_path = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, prefix="codir_rec_", suffix=".bin",
            dir=spool_dir,  # spool sur volume disque, pas tmpfs
        ) as tmp:
            tmp_path = tmp.name
            for c in chunks:
                # Stream chunk-by-chunk depuis le storage source
                c.chunk_file.open("rb")
                try:
                    while True:
                        block = c.chunk_file.read(1024 * 1024)  # 1 Mo
                        if not block:
                            break
                        tmp.write(block)
                        total_bytes += len(block)
                finally:
                    c.chunk_file.close()

        # Sauvegarde le fichier assemblé sur le FileField principal.
        # On utilise une ouverture en mode rb et on laisse Django streamer.
        fname = recording.original_filename or "recording.audio"
        with open(tmp_path, "rb") as assembled:
            try:
                recording.audio_file.save(fname, File(assembled), save=False)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "finalize: save audio_file storage par défaut KO (%s). Fallback FS.",
                    exc,
                )
                media_root = getattr(settings, "MEDIA_ROOT", None) or "/var/www/media"
                os.makedirs(media_root, exist_ok=True)
                fs = FileSystemStorage(location=media_root)
                rel = recording.audio_file.field.upload_to(recording, fname)
                assembled.seek(0)
                saved = fs.save(rel, File(assembled))
                recording.audio_file.name = saved

        recording.file_size = total_bytes
        recording.uploaded_at = timezone.now()
        recording.stopped_at = recording.stopped_at or timezone.now()
        recording.status = RecordingStatus.UPLOADED
        recording.save(update_fields=[
            "audio_file", "file_size", "uploaded_at", "stopped_at", "status",
            "updated_at",
        ])
    except Exception as exc:  # noqa: BLE001
        log.exception("finalize: assemblage KO rec=%s", recording.id)
        try:
            mark_failed(recording, f"Erreur assemblage chunked upload : {exc}")
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:  # noqa: BLE001
                pass

    # Nettoyage des chunks intermédiaires.
    for c in chunks:
        try:
            c.chunk_file.delete(save=False)
        except Exception:  # noqa: BLE001
            pass
    RecordingChunk.unscoped.filter(recording=recording).delete()

    log.info(
        "finalize_chunked: rec=%s total=%s octets / %s chunks assemblés",
        recording.id, total_bytes, total_chunks,
    )

    # Déclenche le pipeline Celery (best-effort).
    try:
        from ..tasks import process_recording_task
        process_recording_task.delay(str(recording.id))
    except Exception:  # noqa: BLE001
        log.exception("finalize: enqueue Celery KO rec=%s", recording.id)
        # On n'échoue pas pour autant : l'audio est sauvegardé, le user peut
        # relancer manuellement via /recordings/{id}/process/.

    return recording


# ─── 5. Abort (cleanup) ───────────────────────────────────────

def abort_chunked_upload(recording: MeetingRecording, *, reason: str = "") -> None:
    """Annule un upload en cours : supprime tous les chunks + marque FAILED."""
    chunks = list(RecordingChunk.unscoped.filter(recording=recording))
    for c in chunks:
        try:
            c.chunk_file.delete(save=False)
        except Exception:  # noqa: BLE001
            pass
    RecordingChunk.unscoped.filter(recording=recording).delete()
    if reason:
        mark_failed(recording, f"Upload chunked annulé : {reason}")
    else:
        update_status(recording, RecordingStatus.FAILED, error="Upload annulé.")
