from django.apps import AppConfig


class WorkflowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workflows"
    verbose_name = "Workflows"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
