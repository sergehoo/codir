"""Production settings."""
from .base import *  # noqa: F401, F403

DEBUG = False

# ─── HTTPS / HSTS ────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# ─── Cookies hardening ───────────────────────────────────────
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8       # 8h
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
# Pour API cross-domain avec credentials, surcharger ces 2 lignes :
# SESSION_COOKIE_SAMESITE = "None"
# CSRF_COOKIE_SAMESITE = "None"

# ─── Storage S3 — chiffrement at-rest forcé ──────────────────
# Surcharge le bloc STORAGES de base.py
# IMPORTANT : on garde la structure 2-storages (default + recordings) définie
# dans base.py, et on ajoute simplement les options spécifiques prod.

# Server-Side Encryption : par défaut désactivé (compat MinIO self-hosted).
# Activer uniquement sur AWS S3 où SSE-S3 / SSE-KMS sont supportés nativement.
# Pour activer : S3_SSE=AES256 dans .env.prod (cas AWS) — laisser vide pour MinIO.
_SSE_MODE = env("S3_SSE", default="")  # noqa: F405

# Construction conditionnelle de object_parameters (chiffrement + cache headers)
_S3_OBJECT_PARAMS = {}
if _SSE_MODE:
    # AES256 (SSE-S3) ou aws:kms — AWS uniquement, NE PAS utiliser avec MinIO
    # standard. Si tu actives ça par erreur sur MinIO → erreur NotImplemented.
    _S3_OBJECT_PARAMS["ServerSideEncryption"] = _SSE_MODE

_S3_COMMON_OPTIONS = {
    "region_name": env("S3_REGION", default="eu-west-1"),  # noqa: F405
    "endpoint_url": env("S3_ENDPOINT", default=None),  # noqa: F405
    "access_key": env("S3_ACCESS_KEY"),  # noqa: F405
    "secret_key": env("S3_SECRET_KEY"),  # noqa: F405
    "default_acl": "private",
    "querystring_auth": True,
    "addressing_style": "path",       # OBLIGATOIRE pour MinIO
    "signature_version": "s3v4",      # OBLIGATOIRE pour MinIO
    "file_overwrite": False,
    "custom_domain": env("S3_PUBLIC_DOMAIN", default=""),  # noqa: F405
    "url_protocol": env("S3_URL_PROTOCOL", default="https:"),  # noqa: F405
    "querystring_expire": env.int("S3_PRESIGN_EXPIRE", default=3600),  # noqa: F405
}
# Ne mettre object_parameters dans les options QUE si non vide — sinon
# django-storages enverra un paramètre vide qui fait planter boto3.
if _S3_OBJECT_PARAMS:
    _S3_COMMON_OPTIONS["object_parameters"] = _S3_OBJECT_PARAMS

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON_OPTIONS,
            "bucket_name": env("S3_BUCKET"),  # noqa: F405
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "recordings": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON_OPTIONS,
            "bucket_name": env(
                "RECORDING_S3_BUCKET",
                default=env("S3_BUCKET", default="codir-recordings-prod"),  # noqa: F405
            ),  # noqa: F405
        },
    },
}

# ─── Email production ────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")  # noqa: F405

# ─── JWT RS256 ───────────────────────────────────────────────
SIMPLE_JWT["ALGORITHM"] = "RS256"  # noqa: F405


def _load_pem_key(env_var: str, path_env_var: str) -> str:
    """
    Charge une clé PEM depuis :
      1. un fichier si <PATH_ENV_VAR> est défini (option recommandée)
      2. sinon depuis <ENV_VAR>, en décodant les ``\\n`` littéraux en vrais newlines

    PyJWT / cryptography requièrent des vrais sauts de ligne dans le PEM.
    """
    import os
    from pathlib import Path

    path = os.environ.get(path_env_var)
    if path:
        return Path(path).read_text()

    raw = env(env_var)  # noqa: F405
    if not raw:
        raise RuntimeError(f"{env_var} non défini")
    # Quand la clé vient d'un .env, les retours-ligne sont encodés "\\n"
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")
    return raw.strip()


SIMPLE_JWT["SIGNING_KEY"] = _load_pem_key("JWT_PRIVATE_KEY", "JWT_PRIVATE_KEY_PATH")
SIMPLE_JWT["VERIFYING_KEY"] = _load_pem_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH")

# ─── Logging — pas de stack-trace en clair ──────────────────
# Sentry capte les erreurs ; les logs Django restent en JSON.
# Sentry SDK déjà initialisé dans base.py si SENTRY_DSN défini.
