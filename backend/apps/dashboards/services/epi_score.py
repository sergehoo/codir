"""
EPI Score v2 — Executive Performance Index pour le COMEX.

Calcule un score 0-100 à partir de 4 sous-scores + 1 pénalité :

    completion_score   (30%)  → % tâches DONE sur les 30 derniers jours
    punctuality_score  (30%)  → % tâches terminées avant deadline
    velocity_score     (20%)  → vitesse moyenne décision → fermeture
    quorum_score       (20%)  → respect quorum sur les CODIR récents
    overdue_penalty    (-)    → -3pts par tâche en retard (cap -30)

Tout est transparent, traçable, et historisable (cf. EpiScoreSnapshot).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Avg, F, Q
from django.utils import timezone

from apps.action_plans.models import ActionTask
from apps.common.enums import (
    ActionTaskStatus, DecisionStatus, MeetingStatus,
)
from apps.decisions.models import Decision
from apps.meetings.models import Meeting
from apps.organizations.models import Organization

logger = logging.getLogger(__name__)

# ─── Pondérations (somme = 100) ──────────────────────────────────────────
W_COMPLETION  = 30
W_PUNCTUALITY = 30
W_VELOCITY    = 20
W_QUORUM      = 20
assert W_COMPLETION + W_PUNCTUALITY + W_VELOCITY + W_QUORUM == 100

# Fenêtres d'analyse
DAYS_TASKS_WINDOW    = 30   # complétion & ponctualité
DAYS_VELOCITY_WINDOW = 60   # vélocité
DAYS_MEETINGS_WINDOW = 90   # quorum

# Pénalité overdue
OVERDUE_PENALTY_PER_TASK = 3
OVERDUE_PENALTY_CAP = 30

# Seuil de vélocité (jours) — 0 jour = 100, ≥30 jours = 0
VELOCITY_MAX_DAYS = 30

# Alerte de chute
DROP_ALERT_THRESHOLD = 10  # points


@dataclass
class EpiScoreResult:
    """Résultat complet du calcul, prêt à être persisté ou envoyé en API."""

    overall_score: int  # 0-100
    completion_score: int
    punctuality_score: int
    velocity_score: int
    quorum_score: int
    overdue_penalty: int

    tasks_total: int
    tasks_done: int
    tasks_done_on_time: int
    tasks_overdue: int
    avg_days_to_close: float
    meetings_total: int
    meetings_quorum_reached: int

    # Pour la transparence côté UI
    weights: dict
    windows: dict
    computed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_pct(numerator: int, denominator: int) -> int:
    """Retourne 0..100 entier, gère la division par zéro."""
    if denominator <= 0:
        return 0
    return max(0, min(100, int(round(numerator * 100 / denominator))))


def _compute_completion_score(organization: Organization, today: date) -> tuple[int, dict]:
    """% tâches DONE parmi celles dues dans la fenêtre [today-30d, today]."""
    since = today - timedelta(days=DAYS_TASKS_WINDOW)

    qs = ActionTask.unscoped.filter(
        organization=organization,
        due_date__gte=since,
        due_date__lte=today,
    )
    total = qs.count()
    done = qs.filter(status=ActionTaskStatus.DONE).count()
    score = _safe_pct(done, total) if total else 100  # pas de tâche = score parfait
    return score, {"tasks_total": total, "tasks_done": done}


def _compute_punctuality_score(organization: Organization, today: date) -> tuple[int, dict]:
    """Parmi les tâches DONE des 30 derniers jours, % terminées avant deadline."""
    since = today - timedelta(days=DAYS_TASKS_WINDOW)

    qs = ActionTask.unscoped.filter(
        organization=organization,
        status=ActionTaskStatus.DONE,
        completed_at__date__gte=since,
        completed_at__date__lte=today,
    )
    done_total = qs.count()
    if done_total == 0:
        return 100, {"tasks_done_on_time": 0}

    on_time = qs.filter(
        Q(due_date__isnull=True) | Q(completed_at__date__lte=F("due_date")),
    ).count()
    score = _safe_pct(on_time, done_total)
    return score, {"tasks_done_on_time": on_time}


def _compute_velocity_score(organization: Organization, today: date) -> tuple[int, dict]:
    """Vélocité = jours moyens entre approbation d'une décision et completion.

    0 jour → score 100. ≥30 jours → score 0. Linéaire entre.
    """
    since = today - timedelta(days=DAYS_VELOCITY_WINDOW)

    qs = Decision.unscoped.filter(
        organization=organization,
        status=DecisionStatus.COMPLETED,
        completed_at__date__gte=since,
        approved_at__isnull=False,
    )
    if not qs.exists():
        return 100, {"avg_days_to_close": 0.0}

    deltas = []
    for d in qs.only("approved_at", "completed_at"):
        if d.approved_at and d.completed_at:
            delta = (d.completed_at - d.approved_at).total_seconds() / 86400
            if delta >= 0:
                deltas.append(delta)

    if not deltas:
        return 100, {"avg_days_to_close": 0.0}

    avg_days = sum(deltas) / len(deltas)
    # 0 day → 100, VELOCITY_MAX_DAYS → 0
    score = max(0, min(100, int(round(100 - (avg_days * 100 / VELOCITY_MAX_DAYS)))))
    return score, {"avg_days_to_close": round(avg_days, 2)}


def _compute_quorum_score(organization: Organization, today: date) -> tuple[int, dict]:
    """% de meetings COMPLETED des 90 derniers jours où quorum_reached=True."""
    since = today - timedelta(days=DAYS_MEETINGS_WINDOW)

    qs = Meeting.unscoped.filter(
        organization=organization,
        status=MeetingStatus.COMPLETED,
        scheduled_start__date__gte=since,
        scheduled_start__date__lte=today,
    )
    total = qs.count()
    if total == 0:
        return 100, {"meetings_total": 0, "meetings_quorum_reached": 0}

    reached = qs.filter(quorum_reached=True).count()
    score = _safe_pct(reached, total)
    return score, {"meetings_total": total, "meetings_quorum_reached": reached}


def _compute_overdue_penalty(organization: Organization, today: date) -> tuple[int, dict]:
    """-3 points par tâche actuellement en retard, plafonné à -30."""
    overdue = ActionTask.unscoped.filter(
        organization=organization,
        due_date__lt=today,
    ).exclude(
        status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED],
    ).count()

    penalty = min(overdue * OVERDUE_PENALTY_PER_TASK, OVERDUE_PENALTY_CAP)
    return penalty, {"tasks_overdue": overdue}


def compute_epi_score(organization: Organization, today: date | None = None) -> EpiScoreResult:
    """Calcule l'EPI Score complet pour une organisation à une date donnée.

    Args:
        organization: l'org cible
        today: date de référence (par défaut localdate())

    Returns:
        EpiScoreResult avec les 4 sous-scores, la pénalité, le score final
        et les compteurs bruts (audit).
    """
    today = today or timezone.localdate()

    completion_score, c = _compute_completion_score(organization, today)
    punctuality_score, p = _compute_punctuality_score(organization, today)
    velocity_score, v = _compute_velocity_score(organization, today)
    quorum_score, q = _compute_quorum_score(organization, today)
    overdue_penalty, o = _compute_overdue_penalty(organization, today)

    weighted_sum = (
        completion_score * W_COMPLETION
        + punctuality_score * W_PUNCTUALITY
        + velocity_score * W_VELOCITY
        + quorum_score * W_QUORUM
    ) / 100  # somme pondérée 0-100

    overall = max(0, min(100, int(round(weighted_sum - overdue_penalty))))

    return EpiScoreResult(
        overall_score=overall,
        completion_score=completion_score,
        punctuality_score=punctuality_score,
        velocity_score=velocity_score,
        quorum_score=quorum_score,
        overdue_penalty=overdue_penalty,
        tasks_total=c["tasks_total"],
        tasks_done=c["tasks_done"],
        tasks_done_on_time=p["tasks_done_on_time"],
        tasks_overdue=o["tasks_overdue"],
        avg_days_to_close=v["avg_days_to_close"],
        meetings_total=q["meetings_total"],
        meetings_quorum_reached=q["meetings_quorum_reached"],
        weights={
            "completion": W_COMPLETION,
            "punctuality": W_PUNCTUALITY,
            "velocity": W_VELOCITY,
            "quorum": W_QUORUM,
        },
        windows={
            "tasks_days": DAYS_TASKS_WINDOW,
            "velocity_days": DAYS_VELOCITY_WINDOW,
            "meetings_days": DAYS_MEETINGS_WINDOW,
        },
        computed_at=timezone.now().isoformat(),
    )


def persist_snapshot(organization: Organization, today: date | None = None) -> tuple[Any, bool, int]:
    """Calcule + persiste un snapshot EPI pour la date donnée.

    Idempotent : update_or_create sur (organization, date).
    Renvoie (snapshot, created, delta_vs_previous).
    """
    from apps.dashboards.models import EpiScoreSnapshot

    today = today or timezone.localdate()
    result = compute_epi_score(organization, today)

    # Chercher snapshot J-1 pour calculer le delta
    previous = (
        EpiScoreSnapshot.unscoped.filter(organization=organization, date__lt=today)
        .order_by("-date").only("overall_score").first()
    )
    delta = result.overall_score - previous.overall_score if previous else 0

    snapshot, created = EpiScoreSnapshot.unscoped.update_or_create(
        organization=organization,
        date=today,
        defaults={
            "overall_score": result.overall_score,
            "completion_score": result.completion_score,
            "punctuality_score": result.punctuality_score,
            "velocity_score": result.velocity_score,
            "quorum_score": result.quorum_score,
            "overdue_penalty": result.overdue_penalty,
            "tasks_total": result.tasks_total,
            "tasks_done": result.tasks_done,
            "tasks_done_on_time": result.tasks_done_on_time,
            "tasks_overdue": result.tasks_overdue,
            "avg_days_to_close": Decimal(str(result.avg_days_to_close)),
            "meetings_total": result.meetings_total,
            "meetings_quorum_reached": result.meetings_quorum_reached,
            "drop_vs_previous": delta,
        },
    )
    return snapshot, created, delta


def get_history(organization: Organization, days: int = 90) -> list[dict]:
    """Retourne l'historique des N derniers snapshots EPI pour la sparkline."""
    from apps.dashboards.models import EpiScoreSnapshot

    since = timezone.localdate() - timedelta(days=days)
    snapshots = (
        EpiScoreSnapshot.unscoped.filter(organization=organization, date__gte=since)
        .order_by("date")
        .values("date", "overall_score", "drop_vs_previous")
    )
    return [
        {
            "date": s["date"].isoformat(),
            "score": s["overall_score"],
            "delta": s["drop_vs_previous"],
        }
        for s in snapshots
    ]
