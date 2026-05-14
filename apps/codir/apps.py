from django.apps import AppConfig


class CodirConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.codir"
    verbose_name = "Codir"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
