"""Agent IA proactif — scrute health_scores et émet des messages d'alerte.

Stratégie :
  - Tourne via Celery beat toutes les 4h (production) ou à la demande.
  - Pour chaque organisation × user actif avec `proactive_agent_enabled=True` :
      1. Récupère la watchlist (top sujets à risque pour l'org).
      2. Filtre les sujets où le user a un intérêt direct (owner / responsible
         / assignee d'une tâche enfant).
      3. Anti-spam : ignore si `ProactiveAlert` existant pour ce target dans
         les `COOLDOWN_DAYS` derniers jours sauf si le score s'est dégradé.
      4. Génère un message IA bref (~80-150 tokens) via Claude, posté dans
         une conversation "proactive" dédiée du user.
      5. Trace dans `ProactiveAlert` pour la dédup et les métriques.

Coût :
  - 1 appel LLM par alerte émise (≈ 200-300 tokens). En pratique 1-3 alertes
    par user par jour, soit ~$0.001/user/jour à tarifs Claude Sonnet.
  - Si Claude indisponible, fallback : on construit un message templaté
    déterministe (pas d'IA, mais l'alerte passe quand même).

Activation :
  - Champ `NotificationPreference.proactive_agent_enabled` (default True).
  - L'utilisateur peut désactiver depuis ses préférences.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Configuration
COOLDOWN_DAYS = 5       # ne pas re-signaler le même sujet avant N jours
MIN_SCORE_DROP = 15     # sauf si le score a chuté d'au moins N points
MAX_ALERTS_PER_RUN = 3  # max d'alertes par user par exécution (anti-spam)
SCORE_THRESHOLD = 60    # on ne signale qu'à partir de ce score (watch & below)


def _user_can_be_alerted(user) -> bool:
    """Vérifie que le user est actif + a activé l'agent proactif."""
    if not user.is_active:
        return False
    try:
        from apps.notifications.models import NotificationPreference
        pref = NotificationPreference.unscoped.filter(user=user).first()
        if pref is None:
            return True  # default-on : si pas de pref, on alerte
        return pref.proactive_agent_enabled and pref.internal_enabled
    except Exception:  # noqa: BLE001
        return True


def _user_is_concerned(user, item: dict) -> bool:
    """Détermine si le user a un intérêt direct sur cet item.

    Évite d'alerter tout le monde sur tout. On ne signale qu'aux concernés :
      - plan : owner du plan OU assignee d'une tâche du plan
      - decision : responsible
    """
    kind = item.get("kind")
    target_id = item.get("id")
    if not target_id:
        return False

    try:
        if kind == "plan":
            from apps.action_plans.models import ActionPlan, ActionTask
            plan = ActionPlan.unscoped.filter(id=target_id).first()
            if not plan:
                return False
            if plan.owner_id == user.id:
                return True
            # Assignee d'une tâche du plan
            return ActionTask.unscoped.filter(
                action_plan=plan, assignee=user,
            ).exclude(status__in=["done", "cancelled"]).exists()
        elif kind == "decision":
            from apps.decisions.models import Decision
            d = Decision.unscoped.filter(id=target_id).first()
            return bool(d and d.responsible_id == user.id)
    except Exception:  # noqa: BLE001
        logger.exception("user_is_concerned KO")
    return False


def _recently_alerted(user, item: dict) -> tuple[bool, Optional[int]]:
    """Vérifie si on a déjà alerté ce user sur ce sujet récemment.

    Retourne (skip, last_score). Si skip=True, on ignore. Sinon on peut
    émettre, en passant `last_score` pour décider si la dégradation justifie
    un nouveau ping (delta ≥ MIN_SCORE_DROP).
    """
    from .models import ProactiveAlert
    cutoff = timezone.now() - timedelta(days=COOLDOWN_DAYS)
    last = (
        ProactiveAlert.unscoped
        .filter(
            user=user,
            target_kind=item["kind"],
            target_id=item["id"],
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )
    if last is None:
        return False, None
    # Si dégradation forte, re-alerter même dans le cooldown
    drop = last.health_score_at_emit - item["score"]
    if drop >= MIN_SCORE_DROP:
        return False, last.health_score_at_emit
    return True, last.health_score_at_emit


def _generate_proactive_message(user, item: dict) -> str:
    """Compose un message IA bref pour l'utilisateur.

    Préférence Claude si dispo, sinon fallback template (sans IA).
    """
    user_first = (user.first_name or user.email or "").strip()
    kind_label = "le plan" if item["kind"] == "plan" else "la décision"
    title = item.get("title") or "(sans titre)"
    reasons = item.get("reasons") or []
    score = item.get("score") or 0
    owner = item.get("owner_name") or ""

    # Tentative LLM (best-effort, fallback template si KO)
    try:
        prompt = _build_claude_prompt(user_first, kind_label, title, score, reasons, owner)
        message = _call_claude_brief(prompt)
        if message and len(message) > 20:
            return message
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claude proactive call KO (fallback template): %s", exc)

    # Fallback : message templaté lisible
    name_part = f"{user_first}, " if user_first else ""
    reasons_part = " — " + reasons[0] if reasons else ""
    relance = (
        f" Souhaitez-vous que je vous prépare un brief pour relancer {owner} ?"
        if owner else " Voulez-vous qu'on planifie un point dessus ?"
    )
    return (
        f"⚠️ {name_part}j'ai détecté un sujet à risque : **{title}** "
        f"({score}/100){reasons_part}.{relance}"
    )


def _build_claude_prompt(user_first, kind_label, title, score, reasons, owner) -> str:
    name = user_first or "l'utilisateur"
    reasons_text = "\n".join(f"- {r}" for r in reasons[:3]) or "- (pas de raison détaillée)"
    owner_text = f"Responsable identifié : {owner}." if owner else "Aucun responsable identifié."
    return f"""Tu es l'assistant exécutif CODIR. Tu rédiges un message proactif court
(2-3 phrases max) à {name} pour signaler {kind_label} suivant qui dérape :

Titre : {title}
Score de santé : {score}/100
{owner_text}

Raisons détectées :
{reasons_text}

Format attendu : ton direct, professionnel, qui propose une action concrète
(relancer, planifier un point, transformer en tâche). Pas de salutation ni de
signature. Démarre par ⚠️ ou un emoji similaire. Maximum 250 caractères."""


def _call_claude_brief(prompt: str) -> str:
    """Appel Claude minimal — 250 tokens max. Retourne "" si indispo."""
    from django.conf import settings
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=250,
            system="Tu es un assistant exécutif. Tes messages sont brefs, directs, actionnables.",
            messages=[{"role": "user", "content": prompt}],
        )
        if resp and resp.content:
            return (resp.content[0].text or "").strip()
    except Exception:  # noqa: BLE001
        logger.exception("Claude proactive call failed")
    return ""


def _get_or_create_proactive_conversation(*, user, organization):
    """Récupère (ou crée) LA conversation "proactive" du user dans cette org.

    Une seule conversation par user × org pour tous les messages proactifs,
    pour ne pas spammer la liste des conversations.
    """
    from .models import AIConversation
    conv = AIConversation.unscoped.filter(
        user=user, organization=organization,
        context_scope="proactive", is_archived=False,
    ).first()
    if conv:
        return conv
    return AIConversation.unscoped.create(
        organization=organization,
        user=user,
        title="Alertes IA proactives",
        context_scope="proactive",
        context_id="",
    )


@transaction.atomic
def emit_alert_for_user(*, user, organization, item: dict):
    """Émet une alerte proactive pour ce user × cet item.

    Crée :
      - AIMessage (role=assistant) dans la conv proactive
      - ProactiveAlert (dédup + audit)
    """
    from .models import AIMessage, ProactiveAlert

    text = _generate_proactive_message(user, item)
    conv = _get_or_create_proactive_conversation(user=user, organization=organization)

    msg = AIMessage.unscoped.create(
        organization=organization,
        conversation=conv,
        role="assistant",
        content_md=text,
        citations_json={
            "proactive": True,
            "target_kind": item["kind"],
            "target_id": item["id"],
            "target_url": item.get("url", ""),
            "score": item["score"],
            "label": item["label"],
        },
    )

    ProactiveAlert.unscoped.create(
        organization=organization,
        user=user,
        target_kind=item["kind"],
        target_id=str(item["id"]),
        reason=(item["reasons"][0] if item["reasons"] else "")[:300],
        health_score_at_emit=item["score"],
        ai_message=msg,
        status="emitted",
    )

    # Touche la conv pour qu'elle remonte
    conv.save(update_fields=["updated_at"])
    return msg


def scan_organization(*, organization) -> dict:
    """Scrute l'org, alerte chaque user concerné. Retourne un résumé.

    Format retour : {"alerts_emitted": N, "users_alerted": N, "items_scanned": N}
    """
    from apps.accounts.models import Membership
    from apps.common.health_score import build_watchlist

    summary = {"alerts_emitted": 0, "users_alerted": 0, "items_scanned": 0,
               "skipped_cooldown": 0, "skipped_not_concerned": 0}

    # Top sujets à risque de l'org
    items = build_watchlist(organization=organization, limit=20)
    items = [i for i in items if i["score"] < SCORE_THRESHOLD]
    summary["items_scanned"] = len(items)
    if not items:
        return summary

    # Pour chaque membre actif, on cherche les sujets qui le concernent
    memberships = (
        Membership.unscoped
        .filter(organization=organization, is_active=True)
        .select_related("user")
    )
    alerted_users = set()
    for m in memberships:
        user = m.user
        if not _user_can_be_alerted(user):
            continue
        emitted_for_user = 0
        for item in items:
            if emitted_for_user >= MAX_ALERTS_PER_RUN:
                break
            if not _user_is_concerned(user, item):
                summary["skipped_not_concerned"] += 1
                continue
            skip, _last_score = _recently_alerted(user, item)
            if skip:
                summary["skipped_cooldown"] += 1
                continue
            try:
                emit_alert_for_user(
                    user=user, organization=organization, item=item,
                )
                summary["alerts_emitted"] += 1
                emitted_for_user += 1
                alerted_users.add(user.id)
            except Exception:  # noqa: BLE001
                logger.exception("emit_alert_for_user KO user=%s item=%s",
                                 user.id, item.get("id"))
    summary["users_alerted"] = len(alerted_users)
    return summary


def scan_all_organizations() -> dict:
    """Point d'entrée pour la tâche Celery — scanne toutes les org actives."""
    from apps.organizations.models import Organization
    total = {"alerts_emitted": 0, "users_alerted": 0, "items_scanned": 0,
             "skipped_cooldown": 0, "skipped_not_concerned": 0,
             "orgs_scanned": 0}
    for org in Organization.objects.filter(is_active=True):
        try:
            s = scan_organization(organization=org)
            for k in ["alerts_emitted", "users_alerted", "items_scanned",
                      "skipped_cooldown", "skipped_not_concerned"]:
                total[k] += s.get(k, 0)
            total["orgs_scanned"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("scan_organization KO org=%s", org.id)
    logger.info("proactive_agent scan_all_organizations summary=%s", total)
    return total
