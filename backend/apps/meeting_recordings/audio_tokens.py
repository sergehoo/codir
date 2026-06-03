"""Helpers de génération + vérification de tokens audio éphémères.

Cas d'usage : la balise HTML `<audio src="...">` ne permet pas d'ajouter de
header `Authorization: Bearer ...`. On joint donc un token signé dans l'URL :

    https://codir.tld/api/v1/recordings/X/audio/?token=<hmac>

Le token est un HMAC-SHA256 sur (recording_id + path + user_id + expiry),
signé avec `SECRET_KEY`. Validité courte (10 min par défaut) → impossible
à réutiliser après expiration ou à partager.

Sécurité :
- Signature HMAC empêche la forge (impossible sans SECRET_KEY).
- Expiry court limite la fenêtre d'exploitation si un token leak.
- Token est lié à un user spécifique → traçabilité audit.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from django.conf import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _hmac(payload: bytes) -> bytes:
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).digest()


def generate_audio_token(*, resource_path: str, user_id, expiry_seconds: int = 600) -> str:
    """Génère un token signé valide N secondes.

    `resource_path` : path REL de la ressource (ex: `/api/v1/recordings/X/audio/`).
                      Lier au path empêche la réutilisation pour un autre fichier.
    `user_id`       : ID du user à qui on délivre le token (audit trail).
    `expiry_seconds`: durée de validité.
    """
    body = {
        "p": resource_path,
        "u": str(user_id),
        "e": int(time.time()) + int(expiry_seconds),
    }
    body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
    sig = _hmac(body_bytes)
    return f"{_b64url_encode(body_bytes)}.{_b64url_encode(sig)}"


def verify_audio_token(*, token: str, resource_path: str) -> dict | None:
    """Vérifie la signature + l'expiration + le path.

    Retourne le payload décodé si valide, None sinon. Le caller peut alors
    récupérer `user_id` pour audit (mais l'auth en tant que telle est validée
    par la signature, pas besoin de reload le user en DB).
    """
    if not token or "." not in token:
        return None
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body_bytes = _b64url_decode(body_b64)
        sig = _b64url_decode(sig_b64)
    except Exception:  # noqa: BLE001
        return None

    expected_sig = _hmac(body_bytes)
    # Comparaison time-safe (anti timing-attack)
    if not hmac.compare_digest(sig, expected_sig):
        return None

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None

    # Vérif expiration
    if int(payload.get("e", 0)) < int(time.time()):
        return None

    # Vérif path : empêche d'utiliser un token généré pour un autre fichier
    if payload.get("p") != resource_path:
        return None

    return payload
