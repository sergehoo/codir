from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_engine"
    verbose_name = "AiEngine"

    def ready(self):
        try:
            from . import signals  # noqa: F401
        except ImportError:
            pass
        # Lot 3 — recherche sémantique : auto-index au save des objets métier
        try:
            from .indexing import install_signals
            install_signals()
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "Semantic indexing signals not installed (non-bloquant)"
            )
