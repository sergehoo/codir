from django.apps import AppConfig


class DecisionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.decisions"
    verbose_name = "Decisions"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
