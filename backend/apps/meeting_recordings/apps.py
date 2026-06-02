"""AppConfig — branche les signaux au démarrage Django."""
from django.apps import AppConfig


class MeetingRecordingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.meeting_recordings"
    verbose_name = "Enregistrements de réunion (audio + IA)"

    def ready(self):  # noqa: D401
        # Import différé pour brancher les signaux post_save / audit.
        from . import signals  # noqa: F401
