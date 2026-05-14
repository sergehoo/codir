from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reports"
    verbose_name = "Reports"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
