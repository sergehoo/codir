from django.apps import AppConfig


class ActionPlansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.action_plans"
    verbose_name = "ActionPlans"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
