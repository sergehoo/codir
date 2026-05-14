"""Dev settings — local."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Email — config hérité de base.py (env-driven).
# Pour basculer en console (logs au lieu de SMTP) :
#   EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Outils dev optionnels (uniquement si installés ET URL wired)
# Pour activer django-debug-toolbar : pip install django-debug-toolbar
# puis ajouter dans config/urls.py :
#   if settings.DEBUG:
#       urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
INTERNAL_IPS = ["127.0.0.1"]

# django-extensions est sans danger sans config supplémentaire
try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS += ["django_extensions"]  # noqa: F405
except ImportError:
    pass
