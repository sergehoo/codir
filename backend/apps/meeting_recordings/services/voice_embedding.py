"""VoiceEmbeddingService — reconnaissance vocale incrémentale via Resemblyzer.

Workflow :
  1. Diarisation AAI produit des SpeakerSegment (SPEAKER_00, SPEAKER_01...)
  2. Sample audio par speaker (8s) est extrait dans `DetectedSpeaker.sample_audio`
  3. `compute_embedding_for_speaker` → vecteur 256-dim Resemblyzer
  4. `find_best_user_match` cherche le VoiceProfile le plus proche (cosine sim)
  5. Si match > seuil → `DetectedSpeaker.suggested_participant` + `voice_match_confidence`
  6. Quand l'user confirme le mapping → `add_sample_to_user_profile`
     enrichit le VoiceProfile avec le nouvel embedding (moyenne pondérée)

Stratégie de tolérance :
  - Si resemblyzer ou librosa n'est pas installé → tout est no-op gracieux,
    le pipeline existant continue de fonctionner (mapping manuel comme avant).
  - Si l'extraction d'embedding plante sur un speaker → log + skip, on
    n'arrête pas le pipeline pour autant.
"""
from __future__ import annotations

import logging
import math
import tempfile
from typing import Optional

from django.conf import settings

from ..models import DetectedSpeaker, MeetingRecording, VoiceProfile, VoiceProfileSample

logger = logging.getLogger(__name__)


# Seuil de matching cosine. Empirique pour Resemblyzer :
#   - > 0.85 : match très confiant (souvent même speaker)
#   - 0.75-0.85 : match probable, à valider visuellement
#   - 0.60-0.75 : douteux, on évite de pré-sélectionner
#   - < 0.60 : pas de match (voix différente)
MATCH_THRESHOLD = float(getattr(settings, "VOICE_MATCH_THRESHOLD", 0.75))

# Si tu veux désactiver complètement la feature (RGPD strict, ou perf),
# mets RECORDING_VOICE_RECOGNITION=False dans .env.prod
ENABLED = bool(getattr(settings, "RECORDING_VOICE_RECOGNITION", True))


# ─── Lazy load du modèle Resemblyzer (1× par process) ────────

_encoder = None


def _get_encoder():
    """Charge l'encoder Resemblyzer (singleton process). Retourne None si KO."""
    global _encoder
    if _encoder is not None:
        return _encoder if _encoder != "FAILED" else None
    if not ENABLED:
        logger.info("VoiceEmbedding désactivé via RECORDING_VOICE_RECOGNITION=False")
        _encoder = "FAILED"
        return None
    try:
        from resemblyzer import VoiceEncoder
        _encoder = VoiceEncoder(device="cpu")
        logger.info("Resemblyzer VoiceEncoder chargé (CPU mode)")
        return _encoder
    except ImportError:
        logger.warning(
            "resemblyzer non installé — la reconnaissance vocale est désactivée. "
            "pip install resemblyzer librosa pour l'activer."
        )
        _encoder = "FAILED"
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resemblyzer load KO : %s", exc)
        _encoder = "FAILED"
        return None


# ─── Extraction embedding ────────────────────────────────────

def compute_embedding_for_speaker(
    speaker: DetectedSpeaker,
) -> Optional[list[float]]:
    """Calcule l'embedding 256-dim depuis le sample_audio du speaker.

    Retourne une liste de 256 floats ou None si :
      - resemblyzer absent
      - sample_audio absent / inaccessible
      - audio trop court (< 1 sec)
      - exception inattendue (loggée)
    """
    encoder = _get_encoder()
    if encoder is None:
        return None
    if not speaker.sample_audio:
        return None
    try:
        import numpy as np
        from resemblyzer import preprocess_wav
    except ImportError:
        return None

    # On télécharge le sample en local pour le passer à preprocess_wav
    tmp_path = None
    try:
        speaker.sample_audio.open("rb")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False, prefix="voice_emb_",
            ) as tmp:
                while True:
                    chunk = speaker.sample_audio.read(64 * 1024)
                    if not chunk:
                        break
                    tmp.write(chunk)
                tmp_path = tmp.name
        finally:
            speaker.sample_audio.close()

        wav = preprocess_wav(tmp_path)
        if wav is None or len(wav) < 16000:  # < 1 sec @ 16kHz
            logger.warning(
                "compute_embedding_for_speaker(%s) : audio trop court (%d samples)",
                speaker.speaker_label, 0 if wav is None else len(wav),
            )
            return None
        emb = encoder.embed_utterance(wav)
        # Normalise en liste de floats Python pour JSON serializable
        return [float(x) for x in emb]
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "compute_embedding_for_speaker(%s) KO : %s",
            speaker.speaker_label, exc,
        )
        return None
    finally:
        if tmp_path:
            try:
                import os
                os.unlink(tmp_path)
            except Exception:  # noqa: BLE001
                pass


# ─── Math ─────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity entre 2 vecteurs (listes de floats). 0..1 attendu."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ─── Matching ─────────────────────────────────────────────────

def find_best_user_match(
    embedding: list[float], *, organization, threshold: float = MATCH_THRESHOLD,
) -> tuple[Optional[VoiceProfile], float]:
    """Cherche le VoiceProfile le plus proche dans l'organisation.

    Retourne (profile, similarity). profile=None si rien au-dessus du seuil.
    """
    if not embedding:
        return None, 0.0
    profiles = list(
        VoiceProfile.unscoped
        .filter(organization=organization, is_active=True)
        .select_related("user")
    )
    best: Optional[VoiceProfile] = None
    best_sim = 0.0
    for p in profiles:
        if not p.embedding:
            continue
        sim = _cosine(embedding, p.embedding)
        if sim > best_sim:
            best_sim = sim
            best = p
    if best_sim >= threshold:
        return best, best_sim
    return None, best_sim  # retourne best_sim même sous le seuil (debug)


# ─── Apprentissage (ajout d'un sample à un profil) ───────────

def add_sample_to_user_profile(
    *, user, organization, embedding: list[float],
    source_recording: Optional[MeetingRecording] = None,
    source_speaker_label: str = "",
    quality_score: float = 1.0,
    added_by=None,
) -> Optional[VoiceProfile]:
    """Ajoute un sample à un VoiceProfile et recalcule l'embedding moyen.

    Crée le profil si nécessaire. Idempotent : un même (recording, speaker_label)
    ne peut pas être ajouté deux fois (on update au lieu d'insérer).
    """
    if not embedding:
        return None
    if not ENABLED:
        return None

    # Get/create profile
    profile, _ = VoiceProfile.unscoped.get_or_create(
        organization=organization, user=user,
        defaults={"embedding": [], "sample_count": 0},
    )

    # Trace le sample (audit + recalcul). Idempotence sur (recording, label).
    existing = None
    if source_recording is not None and source_speaker_label:
        existing = VoiceProfileSample.unscoped.filter(
            voice_profile=profile,
            source_recording=source_recording,
            source_speaker_label=source_speaker_label,
        ).first()

    if existing:
        existing.embedding = embedding
        existing.quality_score = quality_score
        existing.added_by = added_by
        existing.save(update_fields=["embedding", "quality_score", "added_by", "updated_at"])
    else:
        VoiceProfileSample.unscoped.create(
            organization=organization,
            voice_profile=profile,
            source_recording=source_recording,
            source_speaker_label=source_speaker_label,
            embedding=embedding,
            quality_score=quality_score,
            added_by=added_by,
        )

    # Recompute la moyenne pondérée par quality_score
    samples = list(
        VoiceProfileSample.unscoped
        .filter(voice_profile=profile)
        .values_list("embedding", "quality_score")
    )
    if not samples:
        return profile
    dim = len(samples[0][0])
    summed = [0.0] * dim
    total_weight = 0.0
    for emb, w in samples:
        if not emb or len(emb) != dim:
            continue
        for i, v in enumerate(emb):
            summed[i] += v * (w or 1.0)
        total_weight += (w or 1.0)
    if total_weight > 0:
        avg = [v / total_weight for v in summed]
        # Normalise en vecteur unitaire (pour cosine similarity stable)
        norm = math.sqrt(sum(v * v for v in avg))
        if norm > 0:
            avg = [v / norm for v in avg]
        profile.embedding = avg
    profile.sample_count = len(samples)
    profile.save(update_fields=["embedding", "sample_count", "last_updated_at", "updated_at"])

    logger.info(
        "add_sample_to_user_profile : user=%s rec=%s label=%s → profil contient %d samples",
        user.id, source_recording.id if source_recording else None,
        source_speaker_label, profile.sample_count,
    )
    return profile


# ─── API "tout-en-un" pour les hooks ─────────────────────────

def apply_voice_recognition(recording: MeetingRecording) -> int:
    """Pour chaque DetectedSpeaker non-mappé, tente de matcher avec un VoiceProfile.

    Met à jour speaker.suggested_participant + voice_match_confidence.
    Retourne le nombre de speakers pour qui un match confiant a été trouvé.

    Appelée APRÈS aggregate_speakers_from_segments dans le pipeline Celery.
    """
    if not ENABLED:
        return 0
    if _get_encoder() is None:
        return 0

    matches = 0
    for speaker in DetectedSpeaker.unscoped.filter(recording=recording):
        if speaker.mapped_participant_id:
            continue  # déjà mappé manuellement, on ne touche pas
        emb = compute_embedding_for_speaker(speaker)
        if not emb:
            continue
        profile, sim = find_best_user_match(emb, organization=recording.organization)
        if profile is not None:
            speaker.suggested_participant = profile.user
            speaker.voice_match_confidence = float(sim)
            speaker.save(update_fields=[
                "suggested_participant", "voice_match_confidence", "updated_at",
            ])
            matches += 1
            logger.info(
                "Voice match : speaker=%s → user=%s (sim=%.3f)",
                speaker.speaker_label, profile.user_id, sim,
            )
        else:
            # On stocke quand même le best_sim (sous le seuil) pour info debug
            speaker.voice_match_confidence = float(sim)
            speaker.save(update_fields=["voice_match_confidence", "updated_at"])
    return matches
