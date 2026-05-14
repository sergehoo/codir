from django.apps import AppConfig


class MobileApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mobile_api"
    verbose_name = "MobileApi"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
