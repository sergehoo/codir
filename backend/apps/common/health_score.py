"""Health Score — Cockpit prédictif & Watch list.

Calcule un score 0-100 de santé pour les objets pilotables (ActionPlan,
Decision) basé sur des signaux objectifs : retard, inactivité, dérive
deadline, priorité.

Approche conservatrice :
  - Pas d'appel LLM : pure logique métier, déterministe, testable.
  - Score = 100 par défaut, pénalités cumulatives plafonnées.
  - Label dérivé du score : sain / à surveiller / à risque / critique.
  - Retourne aussi `reasons` (list[str]) : les facteurs identifiés, pour
    afficher dans l'UI sous forme de bullets explicatifs.

Utilisé par :
  - Le widget WatchList du cockpit (top sujets à risque).
  - L'agent IA proactif (Lot 2) qui scrute les scores < threshold.
  - Les serializers Plan/Decision qui exposent score + label au frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.utils import timezone

# ─── Constantes ───────────────────────────────────────────────

# Seuils de labellisation
SCORE_HEALTHY = 80   # ≥ 80 → sain
SCORE_WATCH   = 60   # 60-79 → à surveiller
SCORE_AT_RISK = 40   # 40-59 → à risque (< 40 = critique)

# Délais d'inactivité jugés problématiques
INACTIVE_DAYS_WARNING  = 14
INACTIVE_DAYS_CRITICAL = 30

# Priorité = multiplicateur des pénalités (critical pèse plus lourd)
PRIORITY_WEIGHT = {
    "low":      0.7,
    "medium":   1.0,
    "high":     1.2,
    "critical": 1.5,
}


@dataclass
class HealthResult:
    score: int  # 0-100
    label: str  # "healthy" | "watch" | "at_risk" | "critical"
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"score": self.score, "label": self.label, "reasons": self.reasons}


def _label_from_score(score: int) -> str:
    if score >= SCORE_HEALTHY: return "healthy"
    if score >= SCORE_WATCH:   return "watch"
    if score >= SCORE_AT_RISK: return "at_risk"
    return "critical"


def _clamp(v: int) -> int:
    return max(0, min(100, v))


# ─── ActionPlan ───────────────────────────────────────────────

def compute_plan_health(plan) -> HealthResult:
    """Calcule la santé d'un ActionPlan.

    Signaux :
      - dérive deadline : progress_percent vs progrès attendu sur la durée
      - retards de tâches enfants (overdue)
      - inactivité (updated_at)
      - statut on_hold / blocked
    """
    today = timezone.localdate()
    now = timezone.now()
    score = 100
    reasons: list[str] = []

    # ── Plans complétés ou annulés : score figé sain ──
    if plan.status in ("completed", "cancelled"):
        return HealthResult(
            score=100 if plan.status == "completed" else 50,
            label="healthy" if plan.status == "completed" else "watch",
            reasons=[f"Plan {plan.status}"],
        )

    # ── Pénalité statut bloqué / on_hold ──
    if plan.status == "on_hold":
        score -= 20
        reasons.append("Plan en pause (on_hold)")
    elif plan.status == "blocked":
        score -= 35
        reasons.append("Plan bloqué")

    # ── Dérive deadline ──
    if plan.target_end_date:
        days_to_end = (plan.target_end_date - today).days
        if days_to_end < 0:
            # Overdue : retard direct
            score -= 35
            reasons.append(
                f"Échéance dépassée de {-days_to_end}j "
                f"(progress {plan.progress_percent}%)"
            )
            # +1 par jour de retard (cap -15)
            score -= min(-days_to_end, 15)
        else:
            # Pas encore en retard, mais dérive : si la durée totale est connue
            # via created_at → target_end_date, calculer le progrès attendu
            try:
                created = plan.created_at.date() if hasattr(plan.created_at, 'date') else plan.created_at
                total_days = (plan.target_end_date - created).days
                elapsed_days = (today - created).days
                if total_days > 0 and elapsed_days > 0:
                    expected_progress = int(100 * elapsed_days / total_days)
                    actual = plan.progress_percent or 0
                    gap = expected_progress - actual
                    if gap > 25:
                        score -= 20
                        reasons.append(
                            f"Dérive : {actual}% réalisé vs {expected_progress}% attendu"
                        )
                    elif gap > 10:
                        score -= 10
                        reasons.append(
                            f"Léger retard : {actual}% vs {expected_progress}% attendu"
                        )
            except Exception:  # noqa: BLE001
                pass
    elif plan.status == "in_progress":
        # Pas de deadline + en cours = risque modéré (manque de cadrage)
        score -= 5
        reasons.append("Aucune échéance cible")

    # ── Tâches enfants overdue ──
    try:
        from apps.action_plans.models import ActionTask
        from apps.common.enums import ActionTaskStatus
        overdue_count = (
            ActionTask.unscoped
            .filter(action_plan=plan, due_date__lt=today)
            .exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
            .count()
        )
        if overdue_count > 0:
            penalty = min(overdue_count * 5, 25)
            score -= penalty
            reasons.append(f"{overdue_count} tâche(s) en retard")
    except Exception:  # noqa: BLE001
        pass

    # ── Inactivité ──
    if plan.updated_at:
        days_inactive = (now - plan.updated_at).days
        if days_inactive >= INACTIVE_DAYS_CRITICAL:
            score -= 20
            reasons.append(f"Aucune mise à jour depuis {days_inactive}j")
        elif days_inactive >= INACTIVE_DAYS_WARNING:
            score -= 10
            reasons.append(f"Aucune mise à jour depuis {days_inactive}j")

    score = _clamp(score)
    return HealthResult(score=score, label=_label_from_score(score), reasons=reasons)


# ─── Decision ─────────────────────────────────────────────────

def compute_decision_health(decision) -> HealthResult:
    """Calcule la santé d'une Decision.

    Signaux :
      - durée au statut "proposed" (devrait être courte)
      - deadline approchante ou dépassée sans validation
      - priorité critical sans deadline
      - inactivité
    """
    today = timezone.localdate()
    now = timezone.now()
    score = 100
    reasons: list[str] = []

    weight = PRIORITY_WEIGHT.get(decision.priority, 1.0)

    # ── Statut terminal : pas de scoring ──
    if decision.status in ("approved", "implemented"):
        return HealthResult(score=100, label="healthy",
                            reasons=[f"Décision {decision.status}"])
    if decision.status in ("rejected", "cancelled"):
        return HealthResult(score=80, label="healthy",
                            reasons=[f"Décision {decision.status}"])

    # ── Durée au statut proposed ──
    if decision.status == "proposed":
        days_open = (now - decision.created_at).days
        if days_open >= 30:
            score -= int(35 * weight)
            reasons.append(f"Proposée depuis {days_open}j sans décision")
        elif days_open >= 14:
            score -= int(15 * weight)
            reasons.append(f"En attente depuis {days_open}j")
    elif decision.status == "in_review":
        days_open = (now - decision.updated_at).days
        if days_open >= 21:
            score -= int(25 * weight)
            reasons.append(f"En revue depuis {days_open}j")

    # ── Deadline passée ──
    if decision.deadline:
        if decision.deadline < today:
            score -= int(40 * weight)
            reasons.append(
                f"Échéance dépassée de {(today - decision.deadline).days}j "
                f"({decision.priority})"
            )
        elif (decision.deadline - today).days <= 3:
            score -= int(15 * weight)
            reasons.append(f"Échéance dans {(decision.deadline - today).days}j")
    elif decision.priority == "critical":
        score -= 15
        reasons.append("Priorité critique sans échéance définie")

    # ── Inactivité ──
    days_inactive = (now - decision.updated_at).days
    if days_inactive >= INACTIVE_DAYS_CRITICAL:
        score -= 15
        reasons.append(f"Aucune mise à jour depuis {days_inactive}j")
    elif days_inactive >= INACTIVE_DAYS_WARNING and decision.status == "proposed":
        score -= 8
        reasons.append(f"Aucune mise à jour depuis {days_inactive}j")

    score = _clamp(score)
    return HealthResult(score=score, label=_label_from_score(score), reasons=reasons)


# ─── Watchlist : agrège plans + décisions à risque ────────────

def build_watchlist(*, organization, limit: int = 10) -> list[dict]:
    """Retourne les `limit` premiers items à risque de l'organisation.

    Format renvoyé (compatible UI) :
        {
          "kind": "plan" | "decision",
          "id": "...",
          "title": "...",
          "url": "/action-plans/uuid",
          "score": 35,
          "label": "critical",
          "reasons": ["..."],
          "owner_name": "...",
          "priority": "high",
        }

    Trié par score croissant (plus à risque en tête).
    """
    items: list[dict] = []

    # ── ActionPlans ─────────────────────────────────────────
    try:
        from apps.action_plans.models import ActionPlan
        plans = (
            ActionPlan.unscoped
            .filter(organization=organization)
            .exclude(status__in=["completed", "cancelled"])
            .select_related("owner")
        )
        for p in plans:
            h = compute_plan_health(p)
            # On ne garde que les plans à surveiller ou pire (score < 80)
            if h.score >= SCORE_HEALTHY:
                continue
            items.append({
                "kind": "plan",
                "id": str(p.id),
                "title": p.title or "(sans titre)",
                "url": f"/action-plans/{p.id}",
                "score": h.score,
                "label": h.label,
                "reasons": h.reasons,
                "owner_name": (
                    p.owner.get_full_name() if p.owner and hasattr(p.owner, "get_full_name")
                    else (p.owner.email if p.owner else "")
                ),
                "priority": None,
                "progress_percent": p.progress_percent,
            })
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("watchlist plans KO")

    # ── Decisions ───────────────────────────────────────────
    try:
        from apps.decisions.models import Decision
        decisions = (
            Decision.unscoped
            .filter(organization=organization)
            .exclude(status__in=["approved", "implemented", "rejected", "cancelled"])
            .select_related("responsible")
        )
        for d in decisions:
            h = compute_decision_health(d)
            if h.score >= SCORE_HEALTHY:
                continue
            items.append({
                "kind": "decision",
                "id": str(d.id),
                "title": (d.title or "(sans titre)") + f" ({d.ref})" if hasattr(d, "ref") and d.ref else (d.title or ""),
                "url": f"/decisions/{d.id}",
                "score": h.score,
                "label": h.label,
                "reasons": h.reasons,
                "owner_name": (
                    d.responsible.get_full_name() if d.responsible and hasattr(d.responsible, "get_full_name")
                    else (d.responsible.email if d.responsible else "")
                ),
                "priority": d.priority,
                "progress_percent": None,
            })
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("watchlist decisions KO")

    # Tri : score croissant (plus risqué d'abord), à priorité critique en tête
    def sort_key(it):
        prio_rank = 0 if it.get("priority") == "critical" else 1
        return (prio_rank, it["score"])

    items.sort(key=sort_key)
    return items[:limit]
