from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit_logs"
    verbose_name = "AuditLogs"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
