from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.realtime"
    verbose_name = "Realtime"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
