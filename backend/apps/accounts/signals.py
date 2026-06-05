"""Signaux comptes : audit auto des connexions, déconnexions et tentatives échouées.

Connecté au démarrage via apps.AccountsConfig.ready().

Les events sont écrits dans `audit_logs.AuditLog` avec :
  - actor = user (None pour login_failed si email inconnu)
  - action = "login" | "logout" | "login_failed"
  - ip / user_agent = pris dans audit_context si dispo, sinon dans le signal lui-même
"""
from __future__ import annotations

import logging
from contextlib import suppress

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _resolve_org_for_user(user):
    """Retourne la première organisation active du user (ou None).

    On utilise .unscoped car les signaux d'auth s'exécutent souvent hors contexte
    tenant (le user vient de se logguer, ContextVar pas encore set).
    """
    if user is None:
        return None
    try:
        from apps.accounts.models import Membership
        m = (
            Membership.unscoped
            .filter(user=user, is_active=True)
            .select_related("organization")
            .first()
        )
        return m.organization if m else None
    except Exception:  # noqa: BLE001
        return None


def _request_ctx(request):
    """Extrait IP + user-agent depuis la requête (fallback audit_context)."""
    ip, ua = None, ""
    if request is not None:
        try:
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
            ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]
        except Exception:  # noqa: BLE001
            pass
    if not ip or not ua:
        try:
            from core.middleware.audit import audit_context
            ctx = audit_context.get() or {}
            ip = ip or ctx.get("ip")
            ua = ua or ctx.get("user_agent", "")
        except Exception:  # noqa: BLE001
            pass
    return ip, ua


def _write_audit(*, action: str, org, user, description: str, ip: str | None, ua: str):
    """Crée directement un AuditLog (on bypasse le service qui exige tenant courant)."""
    if org is None:
        # Sans org, on ne peut pas attacher le log (le modèle l'exige).
        return
    try:
        from apps.audit_logs.models import AuditLog
        target_type = None
        target_id = ""
        target_repr = ""
        if user is not None:
            target_type = ContentType.objects.get_for_model(user.__class__)
            target_id = str(user.pk)
            target_repr = (user.get_full_name() or user.email or str(user))[:300]
        AuditLog.unscoped.create(
            organization=org,
            actor=user if user and getattr(user, "is_authenticated", False) else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_repr=target_repr,
            description=description,
            diff_json={},
            ip=ip,
            user_agent=ua or "",
        )
    except Exception:  # noqa: BLE001
        logger.exception("AuditLog write failed (action=%s)", action)


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    org = _resolve_org_for_user(user)
    ip, ua = _request_ctx(request)
    label = user.get_full_name() or user.email
    _write_audit(
        action="login", org=org, user=user,
        description=f"Connexion réussie : {label}",
        ip=ip, ua=ua,
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    org = _resolve_org_for_user(user)
    ip, ua = _request_ctx(request)
    label = user.get_full_name() or user.email
    _write_audit(
        action="logout", org=org, user=user,
        description=f"Déconnexion : {label}",
        ip=ip, ua=ua,
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request=None, **kwargs):
    """Tentative échouée : on log par email même si User introuvable."""
    email = ""
    try:
        email = (credentials.get("email") or credentials.get("username") or "").strip().lower()
    except Exception:  # noqa: BLE001
        pass

    user = None
    org = None
    with suppress(Exception):
        from apps.accounts.models import User
        user = User.objects.filter(email__iexact=email).first() if email else None
        org = _resolve_org_for_user(user) if user else None

    ip, ua = _request_ctx(request)
    desc = f"Échec de connexion : {email or '(email inconnu)'}"
    _write_audit(
        action="login_failed", org=org, user=user,
        description=desc,
        ip=ip, ua=ua,
    )
