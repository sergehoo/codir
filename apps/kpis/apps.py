from django.apps import AppConfig


class KpisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kpis"
    verbose_name = "Kpis"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
