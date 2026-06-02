"""RecordingExtractionService — push validation manuelle → modules cibles.

Quand l'utilisateur valide une extraction IA (DRAFT → VALIDATED), on crée
l'objet réel dans decisions/ ou action_plans/ et on archive la référence
dans `created_decision` / `created_action_plan`.

Sécurité : aucun objet créé sans validation explicite.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import (
    AIExtractionStatus, AIExtractionType,
    RecordingAIExtraction,
)

logger = logging.getLogger(__name__)


def _parse_iso_date(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except Exception:  # noqa: BLE001
        return None


def _resolve_user_by_name(organization, full_name: Optional[str]):
    """Essaie de retrouver un utilisateur du tenant par nom complet (best-effort)."""
    if not full_name:
        return None
    try:
        from apps.accounts.models import User
    except Exception:  # noqa: BLE001
        return None
    parts = [p.strip() for p in full_name.split() if p.strip()]
    if not parts:
        return None
    # Match par first_name + last_name dans n'importe quel ordre.
    qs = User.objects.filter(memberships__organization=organization, is_active=True)
    for p in parts:
        qs = qs.filter(
            Q(first_name__iexact=p) | Q(last_name__iexact=p) | Q(email__icontains=p),
        )
    return qs.first()


@transaction.atomic
def push_decision_to_module(
    *, extraction: RecordingAIExtraction, validated_by,
) -> "object":
    """Crée une Decision réelle depuis un brouillon DRAFT et passe l'extraction VALIDATED.

    Retourne l'objet Decision créé. Idempotent : si l'extraction est déjà
    PUSHED, retourne la decision existante.
    """
    if extraction.extraction_type != AIExtractionType.DECISION:
        raise ValueError("Type d'extraction incompatible (attendu: decision).")
    if extraction.created_decision_id:
        return extraction.created_decision

    try:
        from apps.decisions.models import Decision
        from apps.common.enums import DecisionStatus, ImpactLevel, Priority
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Impossible d'importer decisions: {exc}") from exc

    payload = extraction.raw_payload or {}
    title = (payload.get("title") or "")[:300] or "Décision (issue de l'IA)"
    desc = payload.get("description") or ""
    deadline = _parse_iso_date(payload.get("deadline_suggested"))
    priority = (payload.get("priority") or "medium").lower()
    if priority not in dict(Priority.choices):
        priority = "medium"
    responsible = _resolve_user_by_name(
        extraction.organization, payload.get("responsible_suggested"),
    )

    # Génère un REF compatible (DEC-YYYY-NNNN). On approche au mieux —
    # le module decisions a normalement son propre auto-numéroteur via signals,
    # mais on fournit un fallback.
    rec = extraction.recording
    ref = _generate_decision_ref(extraction.organization)

    decision = Decision.unscoped.create(
        organization=extraction.organization,
        ref=ref,
        title=title,
        description_md=desc,
        meeting=rec.meeting,
        priority=priority,
        status=DecisionStatus.PROPOSED,
        responsible=responsible,
        deadline=deadline,
        created_by=validated_by,
    )

    extraction.status = AIExtractionStatus.PUSHED
    extraction.created_decision = decision
    extraction.validated_by = validated_by
    extraction.validated_at = timezone.now()
    extraction.save(update_fields=[
        "status", "created_decision", "validated_by", "validated_at", "updated_at",
    ])
    return decision


def _generate_decision_ref(organization) -> str:
    """DEC-{YYYY}-{count+1:04d} pour l'organisation courante."""
    from apps.decisions.models import Decision
    year = timezone.now().year
    count = Decision.unscoped.filter(
        organization=organization, ref__startswith=f"DEC-{year}-",
    ).count()
    return f"DEC-{year}-{count + 1:04d}"


@transaction.atomic
def push_action_plan_to_module(
    *, extraction: RecordingAIExtraction, validated_by,
    parent_decision=None,
) -> "object":
    """Crée un ActionPlan (+ ActionTask initiale) depuis un brouillon DRAFT.

    Une action IA = un ActionPlan attaché à une décision (modèle existant).
    Si `parent_decision` n'est pas fourni, on essaie de la résoudre via
    payload['linked_decision'] ; sinon on attache à la décision la plus
    récente de la réunion (fallback raisonnable).
    """
    if extraction.extraction_type != AIExtractionType.ACTION:
        raise ValueError("Type d'extraction incompatible (attendu: action).")
    if extraction.created_action_plan_id:
        return extraction.created_action_plan

    try:
        from apps.action_plans.models import ActionPlan, ActionTask
        from apps.common.enums import ActionPlanStatus, ActionTaskStatus, Priority
        from apps.decisions.models import Decision
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Imports action_plans/decisions KO: {exc}") from exc

    payload = extraction.raw_payload or {}
    title = (payload.get("title") or "")[:300] or "Action (issue de l'IA)"
    desc = payload.get("description") or ""
    deadline = _parse_iso_date(payload.get("deadline_suggested"))
    priority = (payload.get("priority") or "medium").lower()
    if priority not in dict(Priority.choices):
        priority = "medium"
    assignee = _resolve_user_by_name(
        extraction.organization, payload.get("responsible_suggested"),
    )

    # Résolution décision parente
    decision = parent_decision
    if decision is None:
        # Essaie via linked_decision
        linked_title = (payload.get("linked_decision") or "").strip()
        if linked_title:
            decision = Decision.unscoped.filter(
                organization=extraction.organization,
                meeting=extraction.recording.meeting,
                title__iexact=linked_title,
            ).first()
    if decision is None:
        decision = Decision.unscoped.filter(
            organization=extraction.organization,
            meeting=extraction.recording.meeting,
        ).order_by("-created_at").first()
    if decision is None:
        # Crée une décision parente "container" pour cette action
        decision = Decision.unscoped.create(
            organization=extraction.organization,
            ref=_generate_decision_ref(extraction.organization),
            title=f"Décision (container) — actions de {extraction.recording.meeting.title}"[:300],
            description_md="Décision conteneur générée automatiquement pour héberger les actions issues de l'enregistrement.",
            meeting=extraction.recording.meeting,
            status="proposed",
            created_by=validated_by,
        )

    # Crée le plan si la décision n'en a pas (relation OneToOne) — sinon réutilise.
    plan, _ = ActionPlan.unscoped.get_or_create(
        decision=decision,
        defaults={
            "organization": extraction.organization,
            "title": f"Plan d'action — {decision.title}"[:300],
            "owner": assignee or validated_by,
            "status": ActionPlanStatus.OPEN,
        },
    )
    task = ActionTask.unscoped.create(
        organization=extraction.organization,
        action_plan=plan,
        title=title,
        description_md=desc,
        priority=priority,
        status=ActionTaskStatus.TODO,
        assignee=assignee,
        due_date=deadline,
    )

    extraction.status = AIExtractionStatus.PUSHED
    extraction.created_action_plan = plan
    extraction.validated_by = validated_by
    extraction.validated_at = timezone.now()
    extraction.save(update_fields=[
        "status", "created_action_plan", "validated_by", "validated_at", "updated_at",
    ])
    return plan
