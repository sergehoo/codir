"""Service Web Push — envoi de notifications natives navigateur (Lot 6).

Stratégie :
  - À l'émission d'une Notification (via notify()), si `push_enabled=True`
    pour le destinataire, on cherche ses PushSubscription actives.
  - Pour chaque subscription, on envoie via `pywebpush` avec un payload JSON
    contenant title/body/url/icon → le service worker affiche la notif et
    gère le clic.
  - Gestion gracieuse :
    * 410 Gone (user a unsubscribe) → on désactive la subscription en base
    * Autre erreur → on log mais on n'échoue pas la notification globale

Le payload est volontairement minimaliste (≤ 4 Ko, limite navigateurs) :
    {
        "title": "Marc vous a assigné une tâche",
        "body": "Préparer le budget Q3 — échéance vendredi",
        "url": "/tasks/uuid",
        "icon": "https://cdn.org/logo.png",  // logo de l'org si branding
        "tag": "task-uuid",  // dédup côté navigateur
    }
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_push(*, notification, dry_run: bool = False) -> dict:
    """Envoie une notif push à toutes les subscriptions actives du recipient.

    Args:
        notification: instance de Notification
        dry_run: ne pas envoyer, juste retourner le payload (tests)

    Returns: {"sent": N, "failed": N, "deactivated": N, "skipped": N}
    """
    from .models import NotificationPreference, PushSubscription

    summary = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0}

    # Check pref user
    try:
        pref = NotificationPreference.unscoped.filter(
            user=notification.recipient,
        ).first()
        if pref and not pref.push_enabled:
            summary["skipped"] += 1
            return summary
    except Exception:  # noqa: BLE001
        pass  # absence de pref = default-on (cas legacy)

    # Check VAPID configurées
    if not getattr(settings, "VAPID_PRIVATE_KEY", "") or not getattr(settings, "VAPID_PUBLIC_KEY", ""):
        summary["skipped"] += 1
        logger.info("Push skipped — VAPID keys non configurées")
        return summary

    subs = PushSubscription.unscoped.filter(
        user=notification.recipient, is_active=True,
    )
    if not subs.exists():
        summary["skipped"] += 1
        return summary

    payload = _build_payload(notification)
    payload_json = json.dumps(payload)

    if dry_run:
        return {**summary, "preview": payload}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — pip install pywebpush")
        summary["skipped"] += subs.count()
        return summary

    vapid_claims = {"sub": getattr(settings, "VAPID_SUBJECT", "mailto:admin@codir.local")}

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload_json,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=dict(vapid_claims),  # pywebpush mute le dict
                ttl=86400,  # 24h
            )
            sub.last_used_at = timezone.now()
            sub.last_error = ""
            sub.save(update_fields=["last_used_at", "last_error", "updated_at"])
            summary["sent"] += 1
        except WebPushException as exc:
            err_code = getattr(getattr(exc, "response", None), "status_code", 0)
            if err_code in (404, 410):
                # User a unsubscribe → on désactive proprement
                sub.is_active = False
                sub.last_error = f"HTTP {err_code} gone"
                sub.save(update_fields=["is_active", "last_error", "updated_at"])
                summary["deactivated"] += 1
            else:
                sub.last_error = str(exc)[:200]
                sub.save(update_fields=["last_error", "updated_at"])
                summary["failed"] += 1
                logger.warning("Push failed user=%s endpoint=%s err=%s",
                               sub.user_id, sub.endpoint[:60], err_code)
        except Exception as exc:  # noqa: BLE001
            sub.last_error = str(exc)[:200]
            sub.save(update_fields=["last_error", "updated_at"])
            summary["failed"] += 1
            logger.exception("Push send KO")

    return summary


def _build_payload(notification) -> dict:
    """Construit le payload JSON envoyé au service worker."""
    org = getattr(notification, "organization", None)
    icon = getattr(org, "logo", "") if org else ""

    # URL : action_url ou link_url, sinon racine
    target_url = (notification.action_url or notification.link_url or "/").strip()
    if not target_url.startswith("/") and not target_url.startswith("http"):
        target_url = "/" + target_url

    # Title : préfixe org si applicable (cohérent avec emails)
    title = notification.title or "Notification"
    org_name = getattr(org, "name", "") if org else ""
    if org_name and org_name not in title:
        title = f"[{org_name}] {title}"

    body = (notification.body or "")[:240]

    return {
        "title": title[:80],
        "body":  body,
        "url":   target_url,
        "icon":  icon or "/icons/icon-192.png",
        "badge": "/icons/badge-72.png",
        # tag = dédup : si une notif avec ce tag arrive, elle remplace la précédente
        "tag":   str(notification.id),
    }
