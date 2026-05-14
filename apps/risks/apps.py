from django.apps import AppConfig


class RisksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.risks"
    verbose_name = "Risks"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
