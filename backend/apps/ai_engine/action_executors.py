"""Executors d'actions confirmées par l'utilisateur.

Chaque action_type a un executor qui :
  - vérifie les permissions du user
  - crée l'objet métier dans le module cible
  - retourne (success, result_obj, error_msg)

Si une action échoue (permission, validation, exception), on log l'erreur
sur AIActionRequest et on garde l'historique.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import AIActionRequest

logger = logging.getLogger(__name__)


def _user_can_create_decision(user, organization) -> bool:
    """Permissions création décision : staff ou is_executive."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or getattr(user, "is_executive", False):
        return True
    # Tout membre actif peut proposer une décision (status=proposed)
    try:
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=user, organization=organization, is_active=True,
        ).exists()
    except Exception:  # noqa: BLE001
        return False


def _user_can_create_task(user, organization) -> bool:
    """Toute tâche peut être créée par un membre actif."""
    return _user_can_create_decision(user, organization)


# ─── Executors ────────────────────────────────────────────────

def execute_create_decision_draft(*, action: AIActionRequest):
    """Crée un Decision(status=PROPOSED) à partir du payload IA."""
    user = action.requested_by
    org = action.organization

    if not _user_can_create_decision(user, org):
        return False, None, "Permission refusée — vous ne pouvez pas créer de décisions."

    payload = action.payload or {}
    title = (payload.get("title") or "").strip()[:250]
    if not title:
        return False, None, "Titre manquant dans la proposition d'action."

    try:
        from apps.decisions.models import Decision
        d = Decision.unscoped.create(
            organization=org,
            title=title,
            description_md=payload.get("description") or "",
            priority=payload.get("priority") or "medium",
            deadline=payload.get("deadline") or None,
            is_confidential=bool(payload.get("is_confidential", False)),
            status="proposed",
            created_by=user,
        )
        return True, d, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("execute_create_decision_draft KO")
        return False, None, f"Erreur création : {type(exc).__name__}: {exc}"


def execute_create_action_task(*, action: AIActionRequest):
    """Crée une ActionTask(status=TODO) standalone.

    Note : ActionTask est attachée à un ActionPlan. Si payload contient
    `action_plan_id` on l'utilise, sinon on tente de créer ou trouver un plan
    "Tâches diverses" pour rattacher (fallback simple — à raffiner).
    """
    user = action.requested_by
    org = action.organization

    if not _user_can_create_task(user, org):
        return False, None, "Permission refusée — vous ne pouvez pas créer de tâches."

    payload = action.payload or {}
    title = (payload.get("title") or "").strip()[:300]
    if not title:
        return False, None, "Titre manquant."

    # Résout l'assignee depuis email si fourni
    assignee = None
    assignee_email = payload.get("assignee_email") or ""
    if assignee_email:
        try:
            from apps.accounts.models import User
            assignee = User.objects.filter(email__iexact=assignee_email.strip()).first()
        except Exception:  # noqa: BLE001
            pass

    # Résout le plan parent (id explicite OU plan fallback "Tâches diverses")
    try:
        from apps.action_plans.models import ActionPlan, ActionTask
        plan = None
        plan_id = payload.get("action_plan_id")
        if plan_id:
            plan = ActionPlan.unscoped.filter(id=plan_id, organization=org).first()
        if plan is None:
            # Fallback : un plan générique "Tâches diverses" par org (créé si absent)
            plan = ActionPlan.unscoped.filter(
                organization=org, title="Tâches diverses",
            ).first()
            if plan is None:
                plan = ActionPlan.unscoped.create(
                    organization=org,
                    title="Tâches diverses",
                    description_md="Plan d'action générique pour les tâches "
                                   "créées hors d'un projet spécifique "
                                   "(notamment via l'Assistant IA).",
                    owner=user,
                )

        task = ActionTask.unscoped.create(
            organization=org,
            action_plan=plan,
            title=title,
            description_md=payload.get("description") or "",
            assignee=assignee,
            due_date=payload.get("due_date") or None,
            priority=payload.get("priority") or "medium",
            status="todo",
        )
        return True, task, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("execute_create_action_task KO")
        return False, None, f"Erreur création : {type(exc).__name__}: {exc}"


def execute_create_action_plan(*, action: AIActionRequest):
    """Crée un ActionPlan standalone."""
    user = action.requested_by
    org = action.organization

    if not _user_can_create_task(user, org):
        return False, None, "Permission refusée."

    payload = action.payload or {}
    title = (payload.get("title") or "").strip()[:300]
    if not title:
        return False, None, "Titre manquant."

    try:
        from apps.action_plans.models import ActionPlan
        plan = ActionPlan.unscoped.create(
            organization=org,
            title=title,
            description_md=payload.get("description") or "",
            target_end_date=payload.get("target_end_date") or None,
            owner=user,
        )
        return True, plan, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("execute_create_action_plan KO")
        return False, None, f"Erreur création : {type(exc).__name__}: {exc}"


# ─── Dispatcher ───────────────────────────────────────────────

EXECUTORS = {
    "create_decision_draft": execute_create_decision_draft,
    "create_action_task":    execute_create_action_task,
    "create_action_plan":    execute_create_action_plan,
}


def execute_action(action: AIActionRequest) -> AIActionRequest:
    """Point d'entrée : exécute l'action si possible, met à jour le statut."""
    if action.status not in ("pending", "confirmed"):
        # Déjà exécutée ou annulée — idempotent
        return action

    executor = EXECUTORS.get(action.action_type)
    if executor is None:
        action.status = "failed"
        action.error_message = f"Action type '{action.action_type}' non supporté."
        action.save(update_fields=["status", "error_message", "updated_at"])
        return action

    try:
        ok, result_obj, err = executor(action=action)
    except Exception as exc:  # noqa: BLE001
        logger.exception("execute_action crash : %s", action.id)
        action.status = "failed"
        action.error_message = f"Exception : {exc}"
        action.save(update_fields=["status", "error_message", "updated_at"])
        return action

    if not ok:
        action.status = "failed"
        action.error_message = err or "Erreur inconnue"
        action.save(update_fields=["status", "error_message", "updated_at"])
        return action

    action.status = "executed"
    action.executed_at = timezone.now()
    if result_obj is not None:
        try:
            ct = ContentType.objects.get_for_model(result_obj.__class__)
            action.result_object_type = f"{ct.app_label}.{ct.model}"
            action.result_object_id = str(result_obj.pk)
        except Exception:  # noqa: BLE001
            pass
    action.save(update_fields=[
        "status", "executed_at", "result_object_type",
        "result_object_id", "updated_at",
    ])
    return action
