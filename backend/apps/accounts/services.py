"""Services métier — gestion administrative des utilisateurs.

Workflows couverts :
- Création d'un user + Membership initial + notification email avec credentials.
- Reset de mot de passe → notification email avec le nouveau MDP temporaire.
- Réaffectation (changement filiale / direction / rôles) → notification email.
- Désactivation / réactivation → notification email.

Convention de design :
- Tous les services génèrent les mots de passe **temporaires** côté serveur
  (avec `secrets`) et forcent `must_change_password=True`.
- Les credentials sont envoyés UNE SEULE fois par email, jamais loggués.
- Les emails utilisent le pipeline `notifications.notify(send_email=True)` avec
  `check_preference=False` pour les emails CRITIQUES (création, reset MDP)
  car l'utilisateur n'a peut-être pas encore configuré ses préférences.
"""
from __future__ import annotations

import logging
import secrets
import string
from typing import Iterable, Optional

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Génération mots de passe temporaires ─────────────────────

# Alphabet sans ambiguïté visuelle (pas de 0/O, I/l/1) pour éviter les erreurs
# de retranscription par les utilisateurs qui lisent depuis l'email.
_PWD_ALPHABET = string.ascii_letters + string.digits + "!@#$%&*+-?"
_PWD_NO_AMBIG = "".join(c for c in _PWD_ALPHABET if c not in "0OIl1")


def generate_temp_password(length: int = 14) -> str:
    """Mot de passe temporaire fort, sans caractères ambigus.

    Garantit au moins : 1 majuscule, 1 minuscule, 1 chiffre, 1 symbole.
    Conforme à la policy par défaut Django (MinimumLengthValidator 12).
    """
    rng = secrets.SystemRandom()
    while True:
        pwd = "".join(rng.choice(_PWD_NO_AMBIG) for _ in range(length))
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "!@#$%&*+-?" for c in pwd)):
            return pwd


# ─── Création utilisateur + membership ────────────────────────

@transaction.atomic
def create_user_with_membership(
    *, organization, created_by,
    email: str, first_name: str = "", last_name: str = "",
    phone_e164: str = "",
    is_executive: bool = False, is_owner: bool = False,
    subsidiary=None, directions: Iterable = (),
    role_codes: Optional[list[str]] = None,
    send_welcome_email: bool = True,
):
    """Crée un User + Membership et envoie l'email de bienvenue avec credentials.

    Retourne `(user, membership, raw_password)`. Le `raw_password` est utilisé
    UNIQUEMENT pour l'email — ne JAMAIS le persister.

    Si un User existe déjà avec cet email :
    - On ne ré-écrase pas son MDP.
    - On lui crée juste le Membership s'il n'en a pas pour cette organisation.
    - L'email envoyé sera "Vous êtes affecté à une nouvelle organisation".
    """
    from apps.accounts.models import Membership, Role, User

    email_norm = email.strip().lower()
    if not email_norm:
        raise ValueError("Email requis.")

    existing = User.objects.filter(email__iexact=email_norm).first()
    raw_password: Optional[str] = None

    if existing is None:
        raw_password = generate_temp_password()
        # Validation Django (policy = min 12 chars, common password, etc.)
        try:
            validate_password(raw_password)
        except DjangoValidationError:
            # Très improbable avec notre generator, mais on fallback
            raw_password = generate_temp_password(16)
        user = User.objects.create(
            email=email_norm,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone_e164=phone_e164.strip(),
            is_executive=is_executive,
            must_change_password=True,
            is_active=True,
        )
        user.set_password(raw_password)
        user.save(update_fields=["password"])
    else:
        user = existing
        # On ne ré-écrase pas un MDP existant — on signale juste que l'affectation
        # change. Le mail aura alors le contenu "réaffectation".

    # Membership unique par (organization, user)
    membership, created = Membership.unscoped.get_or_create(
        organization=organization, user=user,
        defaults={
            "subsidiary": subsidiary,
            "is_owner": is_owner,
            "is_executive": is_executive,
            "is_active": True,
            "invited_by": created_by,
        },
    )
    if not created:
        # Membership existait déjà : on met à jour le périmètre.
        membership.subsidiary = subsidiary or membership.subsidiary
        membership.is_owner = is_owner or membership.is_owner
        membership.is_executive = is_executive or membership.is_executive
        membership.is_active = True
        membership.save()

    # Directions M2M
    if directions:
        membership.directions.set(list(directions))

    # Rôles M2M par codes
    if role_codes:
        roles = list(Role.unscoped.filter(organization=organization, code__in=role_codes))
        if roles:
            membership.roles.set(roles)

    # Notification + email
    if send_welcome_email:
        _send_user_credentials_email(
            user=user, organization=organization,
            raw_password=raw_password,
            membership=membership,
            actor=created_by,
            kind="created" if raw_password else "reassigned",
        )

    # Audit
    _audit(
        action="user_created" if raw_password else "user_reassigned",
        target=user, actor=created_by, organization=organization,
        description=(
            f"Compte créé : {user.email}" if raw_password
            else f"Affectation : {user.email}"
        ),
    )

    return user, membership, raw_password


# ─── Reset mot de passe ───────────────────────────────────────

@transaction.atomic
def reset_user_password(
    *, user, organization, actor=None,
    send_email: bool = True,
) -> str:
    """Génère un nouveau MDP temporaire, force `must_change_password=True`.

    Retourne le MDP en clair (pour l'envoyer par mail — non persisté).
    """
    raw = generate_temp_password()
    try:
        validate_password(raw, user=user)
    except DjangoValidationError:
        raw = generate_temp_password(16)

    user.set_password(raw)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])

    if send_email:
        _send_user_credentials_email(
            user=user, organization=organization,
            raw_password=raw, membership=None, actor=actor,
            kind="password_reset",
        )

    _audit(
        action="password_reset", target=user, actor=actor, organization=organization,
        description=f"MDP réinitialisé pour {user.email}",
    )
    return raw


# ─── Réaffectation ────────────────────────────────────────────

@transaction.atomic
def reassign_membership(
    *, membership, actor=None,
    subsidiary=None, directions: Optional[Iterable] = None,
    role_codes: Optional[list[str]] = None,
    is_owner: Optional[bool] = None,
    is_executive: Optional[bool] = None,
    send_email: bool = True,
):
    """Met à jour le périmètre d'un membership (filiale, directions, rôles).

    Notifie l'utilisateur que son affectation a changé.
    """
    from apps.accounts.models import Role

    updated_fields = []
    if subsidiary is not None or subsidiary == "":
        membership.subsidiary = subsidiary if subsidiary else None
        updated_fields.append("subsidiary")
    if is_owner is not None:
        membership.is_owner = is_owner
        updated_fields.append("is_owner")
    if is_executive is not None:
        membership.is_executive = is_executive
        updated_fields.append("is_executive")
    if updated_fields:
        membership.save(update_fields=updated_fields + ["updated_at"])

    if directions is not None:
        membership.directions.set(list(directions))

    if role_codes is not None:
        roles = list(Role.unscoped.filter(
            organization=membership.organization, code__in=role_codes,
        ))
        membership.roles.set(roles)

    if send_email:
        _send_user_credentials_email(
            user=membership.user, organization=membership.organization,
            raw_password=None, membership=membership, actor=actor,
            kind="reassigned",
        )

    _audit(
        action="user_reassigned", target=membership.user, actor=actor,
        organization=membership.organization,
        description=f"Affectation modifiée : {membership.user.email}",
        diff={"updated_fields": updated_fields},
    )
    return membership


# ─── Désactivation / Réactivation ─────────────────────────────

@transaction.atomic
def deactivate_user(*, user, organization, actor=None, send_email: bool = True):
    """Désactive un User (login impossible) + tous ses memberships de l'org."""
    from apps.accounts.models import Membership

    user.is_active = False
    user.save(update_fields=["is_active"])

    Membership.unscoped.filter(user=user, organization=organization).update(
        is_active=False, updated_at=timezone.now(),
    )

    if send_email:
        _send_user_credentials_email(
            user=user, organization=organization,
            raw_password=None, membership=None, actor=actor,
            kind="deactivated",
        )

    _audit(
        action="user_deactivated", target=user, actor=actor, organization=organization,
        description=f"Compte désactivé : {user.email}",
    )
    return user


@transaction.atomic
def reactivate_user(*, user, organization, actor=None, send_email: bool = True):
    """Réactive un User + son membership principal de l'org."""
    from apps.accounts.models import Membership

    user.is_active = True
    user.save(update_fields=["is_active"])

    Membership.unscoped.filter(user=user, organization=organization).update(
        is_active=True, updated_at=timezone.now(),
    )

    if send_email:
        _send_user_credentials_email(
            user=user, organization=organization,
            raw_password=None, membership=None, actor=actor,
            kind="reactivated",
        )

    _audit(
        action="user_reactivated", target=user, actor=actor, organization=organization,
        description=f"Compte réactivé : {user.email}",
    )
    return user


# ─── Helper audit centralisé (org explicite, bypass tenant context) ──

def _audit(
    *, action: str, target=None, actor=None, organization=None,
    description: str = "", diff: dict | None = None,
):
    """Wrapper audit_log qui passe l'org explicitement.

    `audit_logs.services.log` lit l'org depuis ContextVar — pas toujours set
    quand on est dans un service appelé hors requête HTTP.
    """
    try:
        from django.contrib.contenttypes.models import ContentType

        from apps.audit_logs.models import AuditLog
        from core.middleware.audit import audit_context
        from core.managers.tenant import current_organization

        org = organization or current_organization.get()
        if org is None:
            return None
        ctx = audit_context.get() or {}
        target_type = ContentType.objects.get_for_model(target.__class__) if target else None
        target_id = str(target.pk) if target else ""
        target_repr = (str(target)[:300] if target else "")
        AuditLog.unscoped.create(
            organization=org, actor=actor, action=action,
            target_type=target_type, target_id=target_id, target_repr=target_repr,
            description=description, diff_json=diff or {},
            ip=ctx.get("ip"), user_agent=ctx.get("user_agent", ""),
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit failed (action=%s)", action)


# ─── Helper notification email centralisé ─────────────────────

def _send_user_credentials_email(
    *, user, organization, raw_password: Optional[str],
    membership, actor, kind: str,
):
    """Envoie l'email approprié selon `kind`.

    kinds :
    - "created"        : compte créé, credentials inclus
    - "password_reset" : MDP réinitialisé, credentials inclus
    - "reassigned"     : périmètre modifié, pas de credentials
    - "deactivated"    : compte désactivé
    - "reactivated"    : compte réactivé
    """
    if not user.email:
        return
    try:
        from apps.notifications.models import (
            NotificationEvent, NotificationLevel, NotificationPriority,
        )
        from apps.notifications.services import notify
    except Exception:  # noqa: BLE001
        logger.exception("Impossible d'importer notifications.services")
        return

    site_url = getattr(settings, "FRONTEND_BASE_URL", "https://codir.local").rstrip("/")
    login_url = f"{site_url}/login"
    full_name = (user.get_full_name() or user.email)
    actor_label = ""
    if actor is not None:
        actor_label = actor.get_full_name() or actor.email

    mapping = {
        "created": (
            NotificationEvent.USER_CREATED,
            f"Votre compte CODIR a été créé",
            "user_welcome",
            NotificationLevel.SUCCESS,
            NotificationPriority.HIGH,
        ),
        "password_reset": (
            NotificationEvent.USER_PASSWORD_RESET,
            "Votre mot de passe CODIR a été réinitialisé",
            "user_password_reset",
            NotificationLevel.WARNING,
            NotificationPriority.HIGH,
        ),
        "reassigned": (
            NotificationEvent.USER_REASSIGNED,
            "Votre affectation CODIR a été mise à jour",
            "user_reassigned",
            NotificationLevel.INFO,
            NotificationPriority.NORMAL,
        ),
        "deactivated": (
            NotificationEvent.USER_DEACTIVATED,
            "Votre compte CODIR a été désactivé",
            "user_deactivated",
            NotificationLevel.WARNING,
            NotificationPriority.HIGH,
        ),
        "reactivated": (
            NotificationEvent.USER_REACTIVATED,
            "Votre compte CODIR a été réactivé",
            "user_reactivated",
            NotificationLevel.SUCCESS,
            NotificationPriority.NORMAL,
        ),
    }
    event, subject, template, level, priority = mapping[kind]

    # Périmètre lisible pour le mail (filiale, directions)
    perimeter = ""
    if membership is not None:
        parts = []
        if membership.subsidiary_id:
            parts.append(f"Filiale : {membership.subsidiary.name}")
        directions = list(membership.directions.values_list("name", flat=True))
        if directions:
            parts.append("Directions : " + ", ".join(directions))
        if membership.is_owner:
            parts.append("Rôle : Owner (DG)")
        elif membership.is_executive:
            parts.append("Rôle : Exécutif")
        perimeter = " · ".join(parts)

    context = {
        "user_name": full_name,
        "user_email": user.email,
        "actor_name": actor_label or "Administration CODIR",
        "raw_password": raw_password or "",
        "has_credentials": bool(raw_password),
        "login_url": login_url,
        "perimeter": perimeter,
        "organization_name": getattr(organization, "name", ""),
    }

    notify(
        organization=organization,
        recipient=user,
        event=event,
        title=subject,
        body=(  # body lu en in-app — version courte
            "Vos identifiants vous ont été envoyés par email."
            if raw_password else
            "Vérifiez votre boîte mail pour les détails."
        ),
        level=level, priority=priority,
        channel="email",
        link_url=login_url, action_url=login_url,
        send_email=True,
        email_template=template,
        email_context=context,
        # CRITIQUE : on ne demande pas de pref pour ces emails admin
        # (sinon un user qui a tout coupé ne reçoit jamais ses credentials).
        check_preference=False,
        target=user,
    )
