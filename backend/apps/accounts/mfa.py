"""Services MFA TOTP — compatible Google Authenticator / Authy / 1Password.

Le secret est stocké chiffré (Fernet) dans ``MFADevice.secret_encrypted``.
La clé Fernet est dérivée de ``DJANGO_SECRET_KEY`` — donc rotation du secret
Django invalide tous les MFA existants (par sécurité).

Architecture du flow de login MFA :
    1. POST /auth/login/ avec email + password
       → si user.mfa_enabled : 200 {"mfa_required": true, "challenge_token": "..."}
       → sinon : 200 {"access": "...", "refresh": "..."}
    2. POST /auth/mfa/verify/ avec challenge_token + code
       → 200 {"access": "...", "refresh": "..."}
       → 400 si code invalide

Pour setup :
    1. POST /auth/mfa/setup/ → 200 {"secret": "...", "qr_url": "data:image/png;base64,..."}
    2. L'user scanne le QR avec son app + tape le code
    3. POST /auth/mfa/verify-setup/ avec code → active mfa_enabled=True
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import secrets
import time
from typing import TYPE_CHECKING

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.signing import BadSignature, TimestampSigner

if TYPE_CHECKING:
    from apps.accounts.models import MFADevice, User

logger = logging.getLogger(__name__)

ISSUER = "CODIR Executive"
CHALLENGE_MAX_AGE = 300  # 5 min entre password OK et entrée du code


def _fernet() -> Fernet:
    """Dérive une clé Fernet stable depuis SECRET_KEY pour chiffrer les secrets TOTP."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret: str) -> bytes:
    return _fernet().encrypt(secret.encode())


def decrypt_secret(encrypted: bytes) -> str:
    try:
        return _fernet().decrypt(bytes(encrypted)).decode()
    except (InvalidToken, ValueError):
        raise ValueError("Secret MFA corrompu ou DJANGO_SECRET_KEY a changé.")


# ─── Setup ──────────────────────────────────────────────────────────────

def generate_setup(user: "User") -> dict:
    """Génère un nouveau secret TOTP + QR code pour un utilisateur.

    Crée (ou remplace) un MFADevice non confirmé. L'user doit ensuite
    appeler ``confirm_setup()`` avec un code valide pour activer.

    Returns:
        dict avec ``secret`` (base32) et ``qr_url`` (data URL PNG).
    """
    from apps.accounts.models import MFADevice

    secret = pyotp.random_base32()
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=ISSUER,
    )

    # QR code → PNG → data URL
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    # Stocke (remplace si existe) l'appareil TOTP "en attente de confirmation"
    MFADevice.objects.update_or_create(
        user=user, method="totp",
        defaults={
            "name": "TOTP App",
            "secret_encrypted": encrypt_secret(secret),
            "confirmed": False,
        },
    )

    return {
        "secret": secret,
        "qr_url": qr_data_url,
        "issuer": ISSUER,
        "account": user.email,
    }


def confirm_setup(user: "User", code: str) -> bool:
    """Vérifie le code TOTP pour activer le MFA.

    Si OK : marque MFADevice.confirmed=True + User.mfa_enabled=True.
    Returns True si activé, False si code invalide.
    """
    from apps.accounts.models import MFADevice

    device = MFADevice.objects.filter(user=user, method="totp").first()
    if not device:
        return False

    try:
        secret = decrypt_secret(device.secret_encrypted)
    except ValueError:
        logger.warning("MFA secret corrupted for user_id=%s", user.id)
        return False

    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False

    device.confirmed = True
    device.save(update_fields=["confirmed"])

    user.mfa_enabled = True
    user.mfa_method = "totp"
    user.save(update_fields=["mfa_enabled", "mfa_method"])

    logger.info("MFA TOTP activé pour user_id=%s", user.id)
    return True


def verify_code(user: "User", code: str) -> bool:
    """Vérifie un code TOTP pour un user qui a déjà MFA activé."""
    from apps.accounts.models import MFADevice
    from django.utils import timezone

    device = MFADevice.objects.filter(
        user=user, method="totp", confirmed=True,
    ).first()
    if not device:
        return False
    try:
        secret = decrypt_secret(device.secret_encrypted)
    except ValueError:
        return False
    if pyotp.TOTP(secret).verify(code, valid_window=1):
        device.last_used_at = timezone.now()
        device.save(update_fields=["last_used_at"])
        user.last_mfa_at = timezone.now()
        user.save(update_fields=["last_mfa_at"])
        return True
    return False


def disable_mfa(user: "User") -> None:
    """Désactive complètement le MFA d'un user (supprime ses devices)."""
    from apps.accounts.models import MFADevice
    MFADevice.objects.filter(user=user).delete()
    user.mfa_enabled = False
    user.mfa_method = ""
    user.save(update_fields=["mfa_enabled", "mfa_method"])


# ─── Challenge token (login étape 1 → étape 2) ──────────────────────────

def make_challenge_token(user_id: str) -> str:
    """Crée un token signé temporaire entre login étape 1 (mdp OK) et étape 2 (code MFA).

    Le token expire après CHALLENGE_MAX_AGE secondes (5 min).
    """
    signer = TimestampSigner(salt="mfa-challenge")
    return signer.sign(str(user_id))


def verify_challenge_token(token: str) -> str | None:
    """Décode un challenge token. Retourne user_id ou None si invalide/expiré."""
    signer = TimestampSigner(salt="mfa-challenge")
    try:
        return signer.unsign(token, max_age=CHALLENGE_MAX_AGE)
    except BadSignature:
        return None
