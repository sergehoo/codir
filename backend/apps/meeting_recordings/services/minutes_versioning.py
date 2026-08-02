"""Historisation des comptes rendus IA (lot HIST).

Principe : ``MeetingRecording.summary`` / ``ai_minutes`` portent toujours la
version *courante* du compte rendu. Chaque fois qu'on s'apprête à les écraser
— régénération IA ou édition manuelle — on archive d'abord l'état existant
dans un ``RecordingMinutesVersion``.

L'historique est **append-only** : une restauration ne supprime pas les
versions postérieures, elle en crée une nouvelle (origin=RESTORED) pointant
vers celle qu'elle réinstalle. On garde ainsi une piste d'audit complète.

Fonctions publiques :
  - ``snapshot_current_minutes()``  → archive l'état courant avant écrasement
  - ``restore_version()``           → réinstalle une version antérieure
  - ``list_versions()``             → historique ordonné d'un recording
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
from django.db.models import Max

from ..models import (
    MeetingRecording,
    MinutesVersionOrigin,
    RecordingMinutesVersion,
)

log = logging.getLogger(__name__)


def _next_version_number(recording: MeetingRecording) -> int:
    """Retourne le prochain numéro de version pour ce recording (1-based).

    ⚠ Doit être appelé dans une transaction où la ligne ``recording`` est
    verrouillée (cf. ``_lock_recording``). Sans ce verrou, deux snapshots
    concurrents — typiquement la tâche Celery de régénération et un PATCH
    /minutes/ utilisateur — calculent le même Max() et violent la contrainte
    unique (recording, version_number).
    """
    current_max = (
        RecordingMinutesVersion.unscoped
        .filter(recording=recording)
        .aggregate(m=Max("version_number"))
        .get("m")
    )
    return (current_max or 0) + 1


def _lock_recording(recording: MeetingRecording) -> None:
    """Pose un verrou pessimiste sur la ligne du recording.

    Sérialise les créations de version concurrentes. Best-effort : sur un
    backend sans support (SQLite en test), on ignore silencieusement.
    """
    try:
        MeetingRecording.unscoped.select_for_update().filter(
            pk=recording.pk,
        ).exists()
    except Exception:  # noqa: BLE001
        log.debug("select_for_update indisponible, poursuite sans verrou")


@transaction.atomic
def snapshot_current_minutes(
    *,
    recording: MeetingRecording,
    origin: str = MinutesVersionOrigin.AI_GENERATED,
    created_by=None,
    label: str = "",
    restored_from: Optional[RecordingMinutesVersion] = None,
) -> Optional[RecordingMinutesVersion]:
    """Archive le CR courant du recording en nouvelle version.

    Ne fait rien (retourne None) si le recording n'a aucun contenu à archiver
    — inutile de polluer l'historique avec des versions vides.

    Idempotence : si la dernière version enregistrée a exactement le même
    contenu, on ne recrée pas de doublon. Évite d'empiler des versions
    identiques quand l'utilisateur sauve sans avoir rien changé.
    """
    summary = (recording.summary or "").strip()
    minutes = (recording.ai_minutes or "").strip()
    if not summary and not minutes:
        return None

    # Verrou pessimiste : sérialise les snapshots concurrents (Celery + PATCH).
    _lock_recording(recording)

    last = (
        RecordingMinutesVersion.unscoped
        .filter(recording=recording)
        .order_by("-version_number")
        .first()
    )
    if last and (last.summary or "").strip() == summary \
            and (last.ai_minutes or "").strip() == minutes:
        log.debug(
            "snapshot: contenu identique à v%s, pas de nouvelle version (rec=%s)",
            last.version_number, recording.id,
        )
        return last

    version = RecordingMinutesVersion.unscoped.create(
        organization=recording.organization,
        recording=recording,
        version_number=_next_version_number(recording),
        summary=recording.summary or "",
        ai_minutes=recording.ai_minutes or "",
        origin=origin,
        created_by=created_by,
        label=label,
        restored_from=restored_from,
    )
    log.info(
        "snapshot CR v%s créée (rec=%s, origin=%s, %d chars)",
        version.version_number, recording.id, origin, version.char_count,
    )
    return version


@transaction.atomic
def restore_version(
    *,
    recording: MeetingRecording,
    version: RecordingMinutesVersion,
    user=None,
) -> MeetingRecording:
    """Réinstalle une version antérieure comme CR courant.

    Avant d'écraser, on snapshot l'état actuel (pour ne rien perdre), puis on
    copie le contenu de ``version`` dans le recording et on trace une nouvelle
    version marquée RESTORED.
    """
    if version.recording_id != recording.id:
        raise ValueError("Cette version n'appartient pas à cet enregistrement.")

    _lock_recording(recording)

    # Court-circuit : la version demandée est déjà le contenu courant.
    # Sans ce garde-fou, restaurer une version identique à l'état actuel
    # empilerait deux versions au contenu rigoureusement identique.
    already_current = (
        (recording.summary or "").strip() == (version.summary or "").strip()
        and (recording.ai_minutes or "").strip() == (version.ai_minutes or "").strip()
    )
    if already_current:
        log.info(
            "restore: v%s est déjà le contenu courant (rec=%s), no-op",
            version.version_number, recording.id,
        )
        return recording

    # 1. Sauve l'état courant avant de l'écraser.
    snapshot_current_minutes(
        recording=recording,
        origin=MinutesVersionOrigin.MANUAL_EDIT,
        created_by=user,
        label="Avant restauration",
    )

    # 2. Réinstalle le contenu de la version choisie.
    recording.summary = version.summary
    recording.ai_minutes = version.ai_minutes
    recording.save(update_fields=["summary", "ai_minutes", "updated_at"])

    # 3. Trace la restauration comme nouvelle version.
    RecordingMinutesVersion.unscoped.create(
        organization=recording.organization,
        recording=recording,
        version_number=_next_version_number(recording),
        summary=version.summary,
        ai_minutes=version.ai_minutes,
        origin=MinutesVersionOrigin.RESTORED,
        created_by=user,
        label=f"Restauration de la v{version.version_number}",
        restored_from=version,
    )
    log.info(
        "CR restauré depuis v%s (rec=%s, par=%s)",
        version.version_number, recording.id, getattr(user, "id", None),
    )
    return recording


def list_versions(recording: MeetingRecording):
    """Historique complet d'un recording, de la plus récente à la plus ancienne."""
    return (
        RecordingMinutesVersion.unscoped
        .filter(recording=recording)
        .select_related("created_by", "restored_from")
        .order_by("-version_number")
    )
