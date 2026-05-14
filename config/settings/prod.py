"""Production settings."""
from .base import *  # noqa: F401, F403

DEBUG = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Email production : SES ou SendGrid via env
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")  # noqa: F405

# JWT en RS256 en prod
SIMPLE_JWT["ALGORITHM"] = "RS256"  # noqa: F405
SIMPLE_JWT["SIGNING_KEY"] = env("JWT_PRIVATE_KEY")  # noqa: F405
SIMPLE_JWT["VERIFYING_KEY"] = env("JWT_PUBLIC_KEY")  # noqa: F405
