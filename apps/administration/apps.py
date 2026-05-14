from django.apps import AppConfig


class AdministrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.administration"
    verbose_name = "Administration"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
