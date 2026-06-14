"""Context loaders — pré-chargent des données métier pour enrichir le prompt IA.

Stratégie :
  - Chaque loader retourne un texte structuré (Markdown) prêt à être inséré
    dans le prompt système du LLM.
  - Tous les loaders sont tenant-safe : ils filtrent par `organization` (et
    par `user` pour les données personnelles) sans dépendre du TenantManager
    (on utilise `.unscoped` car on est dans un service async/sync mixed).
  - Pas de fallback : si la requête échoue, on retourne une chaîne vide
    (un loader cassé ne doit pas casser tout le chat).

Format de sortie type :
    ## Mes tâches en retard (5)
    - **Audit ISO 27001** — Direction : DSI — Échéance : 2026-05-15 (3j de retard)
    - **Budget Q3** — DAF — 2026-05-20 (1j de retard)
    ...

Cette approche évite les "tool calls" complexes (qui nécessitent 2 appels LLM)
en injectant les données directement dans le contexte avant le seul appel LLM.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

# Limites pour ne pas faire exploser le prompt
MAX_ITEMS_PER_SECTION = 10


def _safe_call(fn, *args, **kwargs) -> str:
    """Exécute un loader en attrapant tout — un loader cassé ne doit pas
    faire échouer toute la requête de chat."""
    try:
        return fn(*args, **kwargs) or ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("Context loader %s failed: %s", fn.__name__, exc)
        return ""


# ─── My Tasks ─────────────────────────────────────────────────

def get_my_tasks_context(*, user, organization) -> str:
    """Liste les tâches actives assignées au user."""
    from apps.action_plans.models import ActionTask
    from apps.common.enums import ActionTaskStatus

    qs = (
        ActionTask.unscoped
        .filter(
            organization=organization,
            assignee=user,
            status__in=[ActionTaskStatus.TODO, ActionTaskStatus.IN_PROGRESS,
                        ActionTaskStatus.BLOCKED, ActionTaskStatus.OVERDUE],
        )
        .order_by("due_date", "-created_at")[:MAX_ITEMS_PER_SECTION]
    )
    items = list(qs)
    if not items:
        return ""

    lines = [f"## Mes tâches actives ({len(items)})"]
    for t in items:
        plan_title = ""
        try:
            plan_title = (t.action_plan.title or "")[:60]
        except Exception:  # noqa: BLE001
            pass
        due = t.due_date.isoformat() if t.due_date else "(sans date)"
        status_label = {
            "todo": "À faire",
            "in_progress": "En cours",
            "blocked": "Bloqué",
            "overdue": "En retard",
        }.get(t.status, t.status)
        lines.append(
            f"- **{t.title[:80]}** — Statut : {status_label} — "
            f"Échéance : {due}"
            + (f" — Dossier : {plan_title}" if plan_title else "")
        )
    return "\n".join(lines)


# ─── Overdue Tasks (toute l'org) ──────────────────────────────

def get_overdue_tasks_context(*, user, organization) -> str:
    """Liste les tâches en retard de l'organisation (toutes assignations)."""
    from apps.action_plans.models import ActionTask
    from apps.common.enums import ActionTaskStatus

    today = timezone.localdate()
    qs = (
        ActionTask.unscoped
        .filter(organization=organization, due_date__lt=today)
        .exclude(status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED])
        .select_related("assignee", "action_plan")
        .order_by("due_date")[:MAX_ITEMS_PER_SECTION]
    )
    items = list(qs)
    if not items:
        return ""

    lines = [f"## Tâches en retard ({len(items)} dans l'organisation)"]
    for t in items:
        assignee = ""
        if t.assignee_id:
            assignee = (
                t.assignee.get_full_name() if hasattr(t.assignee, "get_full_name")
                else (t.assignee.email or "?")
            )[:50]
        days_late = (today - t.due_date).days if t.due_date else 0
        lines.append(
            f"- **{t.title[:80]}** — Responsable : {assignee or '?'} — "
            f"Échéance : {t.due_date.isoformat() if t.due_date else '?'} "
            f"({days_late}j de retard)"
        )
    return "\n".join(lines)


# ─── Pending Decisions ────────────────────────────────────────

def get_pending_decisions_context(*, user, organization) -> str:
    """Décisions en attente de validation."""
    from apps.decisions.models import Decision

    qs = (
        Decision.unscoped
        .filter(organization=organization, status__in=["proposed"])
        .select_related("responsible")
        .order_by("-priority", "deadline")[:MAX_ITEMS_PER_SECTION]
    )
    items = list(qs)
    if not items:
        return ""

    lines = [f"## Décisions à valider ({len(items)})"]
    for d in items:
        responsible = ""
        if d.responsible_id and hasattr(d.responsible, "get_full_name"):
            responsible = d.responsible.get_full_name() or d.responsible.email or ""
        deadline = d.deadline.isoformat() if d.deadline else "(sans échéance)"
        prio_label = {
            "critical": "🔴 CRITIQUE", "high": "🟠 Élevée",
            "medium": "🟡 Moyenne", "low": "Faible",
        }.get(d.priority, d.priority)
        lines.append(
            f"- **{(d.title or '')[:80]}** ({d.ref}) — {prio_label} — "
            f"Responsable : {responsible or '?'} — Échéance : {deadline}"
        )
    return "\n".join(lines)


# ─── Upcoming Meetings ────────────────────────────────────────

def get_upcoming_meetings_context(*, user, organization) -> str:
    """Réunions à venir dans les 14 prochains jours."""
    from datetime import timedelta

    from apps.meetings.models import Meeting

    now = timezone.now()
    horizon = now + timedelta(days=14)
    qs = (
        Meeting.unscoped
        .filter(
            organization=organization,
            scheduled_start__gte=now,
            scheduled_start__lte=horizon,
        )
        .exclude(status__in=["cancelled"])
        .order_by("scheduled_start")[:MAX_ITEMS_PER_SECTION]
    )
    items = list(qs)
    if not items:
        return ""

    lines = [f"## Réunions à venir (14 prochains jours, {len(items)})"]
    for m in items:
        when = m.scheduled_start.strftime("%d/%m %H:%M") if m.scheduled_start else ""
        lines.append(f"- **{(m.title or '')[:80]}** — {when} — Statut : {m.status}")
    return "\n".join(lines)


# ─── My Action Plans ──────────────────────────────────────────

def get_my_action_plans_context(*, user, organization) -> str:
    """Plans d'action dont le user est owner."""
    from apps.action_plans.models import ActionPlan

    qs = (
        ActionPlan.unscoped
        .filter(organization=organization, owner=user)
        .exclude(status__in=["completed", "cancelled"])
        .order_by("-created_at")[:MAX_ITEMS_PER_SECTION]
    )
    items = list(qs)
    if not items:
        return ""

    lines = [f"## Mes plans d'action / dossiers ({len(items)})"]
    for p in items:
        end = p.target_end_date.isoformat() if p.target_end_date else "(sans échéance)"
        lines.append(
            f"- **{p.title[:80]}** — {p.progress_percent}% — "
            f"Statut : {p.status} — Échéance : {end}"
        )
    return "\n".join(lines)


# ─── Baseline (toujours inclus) ───────────────────────────────

def get_baseline_summary(*, user, organization) -> str:
    """Mini résumé toujours inclus dans le contexte : 4-5 chiffres clés."""
    from datetime import timedelta

    from apps.action_plans.models import ActionTask
    from apps.common.enums import ActionTaskStatus
    from apps.decisions.models import Decision
    from apps.meetings.models import Meeting

    today = timezone.localdate()
    now = timezone.now()

    try:
        my_tasks = ActionTask.unscoped.filter(
            organization=organization, assignee=user,
            status__in=[ActionTaskStatus.TODO, ActionTaskStatus.IN_PROGRESS,
                        ActionTaskStatus.BLOCKED, ActionTaskStatus.OVERDUE],
        ).count()
        overdue_org = ActionTask.unscoped.filter(
            organization=organization, due_date__lt=today,
        ).exclude(
            status__in=[ActionTaskStatus.DONE, ActionTaskStatus.CANCELLED],
        ).count()
        pending_decisions = Decision.unscoped.filter(
            organization=organization, status="proposed",
        ).count()
        upcoming_meetings = Meeting.unscoped.filter(
            organization=organization,
            scheduled_start__gte=now,
            scheduled_start__lte=now + timedelta(days=7),
        ).exclude(status="cancelled").count()

        return (
            f"## Chiffres clés (aujourd'hui)\n"
            f"- Mes tâches actives : {my_tasks}\n"
            f"- Tâches en retard (org) : {overdue_org}\n"
            f"- Décisions à valider : {pending_decisions}\n"
            f"- Réunions à venir (7j) : {upcoming_meetings}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("baseline_summary KO: %s", exc)
        return ""


# ─── Export d'API utilisée par le router ──────────────────────

LOADERS = {
    "my_tasks":          get_my_tasks_context,
    "overdue_tasks":     get_overdue_tasks_context,
    "pending_decisions": get_pending_decisions_context,
    "upcoming_meetings": get_upcoming_meetings_context,
    "my_action_plans":   get_my_action_plans_context,
    "baseline":          get_baseline_summary,
}


def run_loaders(
    loader_names: list[str], *, user, organization,
) -> tuple[str, list[str]]:
    """Exécute les loaders demandés et concatène leurs sorties.

    Retourne (texte_combiné, noms_loaders_qui_ont_produit_du_contenu).
    """
    sections: list[str] = []
    produced: list[str] = []
    for name in loader_names:
        fn = LOADERS.get(name)
        if fn is None:
            continue
        text = _safe_call(fn, user=user, organization=organization)
        if text and text.strip():
            sections.append(text.strip())
            produced.append(name)
    return ("\n\n".join(sections), produced)
