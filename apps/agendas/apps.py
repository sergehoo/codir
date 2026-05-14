from django.apps import AppConfig


class AgendasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agendas"
    verbose_name = "Agendas"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
