from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.budgets"
    verbose_name = "Budgets"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
