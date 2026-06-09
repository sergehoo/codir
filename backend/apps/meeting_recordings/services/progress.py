"""ProgressService — estime l'avancement % pour chaque étape du pipeline.

Le calcul utilise :
  1. La durée audio (`duration_seconds`) pour pondérer les étapes longues
     (transcription est ~1× la durée audio, diarisation est constante, etc.)
  2. Le temps écoulé depuis `processing_started_at` ou `uploaded_at`
  3. Une table de durées attendues par étape

Si on n'a pas de `duration_seconds` (audio pas encore analysé), on tombe sur
des estimations conservatrices (10 min par défaut).

Le frontend reçoit :
  - step_index / total_steps : 1-based pour affichage "3/6"
  - step_label : nom français lisible
  - step_progress : 0-100 pour la barre de progression
  - eta_seconds : temps restant estimé sur l'étape courante
  - overall_progress : 0-100 sur l'ensemble du pipeline
"""
from __future__ import annotations

from typing import Optional

from django.utils import timezone

from ..models import MeetingRecording, RecordingStatus


# ─── Définition des étapes ──────────────────────────────────────
# (status_value, label, weight, duration_fn)
# weight : poids relatif sur la progression globale (somme = 100)
# duration_fn(audio_seconds) : durée attendue de l'étape en secondes

def _dur_upload(audio_sec: float) -> float:
    """Upload : très variable selon réseau. Estim 1 Mo/s côté serveur."""
    # On approxime via la taille : audio webm 256kbps stereo ≈ 32 KB/s
    estimated_mb = max(5.0, (audio_sec * 32) / 1024.0)
    return max(10.0, estimated_mb)  # ~1 Mo/s minimum


def _dur_transcribe(audio_sec: float) -> float:
    """AAI transcription : ~1× la durée audio (modèle universal-2)."""
    return max(60.0, audio_sec * 0.85)


def _dur_diarize(audio_sec: float) -> float:
    """Diarisation + extraction samples : ~2 min de base + 5s par minute audio."""
    return max(30.0, 60.0 + audio_sec / 12.0)


def _dur_final_transcript(audio_sec: float) -> float:
    """Génération transcript_final : très rapide (boucle Python)."""
    return 15.0


def _dur_summary(audio_sec: float) -> float:
    """Appel LLM Claude/DeepSeek : 30-90s selon la longueur du texte."""
    return max(30.0, 30.0 + audio_sec / 60.0)


def _dur_extract(audio_sec: float) -> float:
    """Extractions décisions/actions : ~2 appels LLM."""
    return max(45.0, 45.0 + audio_sec / 60.0)


# Ordre canonique des étapes du pipeline
STEPS = [
    {"label": "Téléversement",          "weight": 5,  "dur_fn": _dur_upload,
     "statuses": [RecordingStatus.UPLOADING, RecordingStatus.UPLOADED]},
    {"label": "Préparation audio",      "weight": 5,  "dur_fn": _dur_diarize,
     "statuses": [RecordingStatus.PROCESSING]},
    {"label": "Transcription",          "weight": 50, "dur_fn": _dur_transcribe,
     "statuses": [RecordingStatus.TRANSCRIBING]},
    {"label": "Détection des voix",     "weight": 10, "dur_fn": _dur_diarize,
     "statuses": [RecordingStatus.DIARIZING]},
    {"label": "Identification (vous)",  "weight": 0,  "dur_fn": _dur_final_transcript,
     "statuses": [RecordingStatus.WAITING_SPEAKER_MAPPING]},
    {"label": "Transcript final",       "weight": 5,  "dur_fn": _dur_final_transcript,
     "statuses": [RecordingStatus.GENERATING_FINAL_TRANSCRIPT]},
    {"label": "Résumé IA",              "weight": 15, "dur_fn": _dur_summary,
     "statuses": [RecordingStatus.SUMMARIZING]},
    {"label": "Décisions & actions",    "weight": 10, "dur_fn": _dur_extract,
     "statuses": [RecordingStatus.EXTRACTING_ACTIONS]},
]


def _find_step(status: str) -> Optional[int]:
    for i, step in enumerate(STEPS):
        if status in step["statuses"]:
            return i
    return None


def compute_progress(recording: MeetingRecording) -> dict:
    """Retourne le dict de progression pour le payload /status/."""
    status = recording.status

    # Terminal states
    if status == RecordingStatus.COMPLETED:
        return {
            "step_index": len(STEPS),
            "total_steps": len(STEPS),
            "step_label": "Terminé",
            "step_progress": 100,
            "overall_progress": 100,
            "eta_seconds": 0,
        }
    if status == RecordingStatus.FAILED:
        idx = _find_step(status) or 0
        return {
            "step_index": idx + 1,
            "total_steps": len(STEPS),
            "step_label": "Échec",
            "step_progress": 0,
            "overall_progress": int(_sum_weights_before(idx)),
            "eta_seconds": 0,
        }
    if status == RecordingStatus.CREATED:
        return {
            "step_index": 1,
            "total_steps": len(STEPS),
            "step_label": "Initialisation",
            "step_progress": 0,
            "overall_progress": 0,
            "eta_seconds": None,
        }
    if status == RecordingStatus.WAITING_SPEAKER_MAPPING:
        # Bloqué sur action utilisateur — progression = somme des poids passés
        idx = _find_step(status) or 4
        return {
            "step_index": idx + 1,
            "total_steps": len(STEPS),
            "step_label": "Identification des voix (vous)",
            "step_progress": 0,
            "overall_progress": int(_sum_weights_before(idx)),
            "eta_seconds": None,  # dépend de l'utilisateur
        }

    # Step courant
    idx = _find_step(status)
    if idx is None:
        return {
            "step_index": 1,
            "total_steps": len(STEPS),
            "step_label": "En cours…",
            "step_progress": 0,
            "overall_progress": 0,
            "eta_seconds": None,
        }

    step = STEPS[idx]
    audio_sec = float(recording.duration_seconds or 0)
    if audio_sec <= 0:
        # Fallback : audio non encore analysé, on assume 10 min
        audio_sec = 600.0
    expected_dur = step["dur_fn"](audio_sec)

    # Temps écoulé sur l'étape : on utilise le dernier transition timestamp
    # disponible (updated_at est touché à chaque update_status).
    started = recording.processing_started_at or recording.uploaded_at or recording.created_at
    elapsed = (timezone.now() - started).total_seconds() if started else 0
    # On clamp pour qu'on ne descend jamais en dessous d'une vague animation
    step_pct = max(2, min(95, int((elapsed / expected_dur) * 100)))

    eta = max(0, int(expected_dur - elapsed))

    # Overall = somme poids étapes passées + partie de l'étape courante
    overall = _sum_weights_before(idx) + (step["weight"] * step_pct / 100.0)
    overall = max(0, min(99, int(overall)))

    return {
        "step_index": idx + 1,
        "total_steps": len(STEPS),
        "step_label": step["label"],
        "step_progress": step_pct,
        "overall_progress": overall,
        "eta_seconds": eta,
    }


def _sum_weights_before(idx: int) -> float:
    return sum(s["weight"] for s in STEPS[:idx])
