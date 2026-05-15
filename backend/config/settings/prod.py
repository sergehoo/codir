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
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("S3_BUCKET"),  # noqa: F405
            "region_name": env("S3_REGION", default="eu-west-1"),  # noqa: F405
            "endpoint_url": env("S3_ENDPOINT", default=None),  # noqa: F405
            "access_key": env("S3_ACCESS_KEY"),  # noqa: F405
            "secret_key": env("S3_SECRET_KEY"),  # noqa: F405
            "default_acl": "private",
            "querystring_auth": True,
            "object_parameters": {
                "ServerSideEncryption": env("S3_SSE", default="AES256"),  # noqa: F405
                # Cache long pour assets, pas pour docs :
                # "CacheControl": "max-age=3600",
            },
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
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
