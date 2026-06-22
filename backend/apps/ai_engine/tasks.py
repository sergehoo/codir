"""Celery tasks pour l'agent IA proactif (Lot 2)."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.ai_engine.tasks.proactive_agent_scan",
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 2},
)
def proactive_agent_scan():
    """Scan toutes les org actives et émet les alertes proactives nécessaires.

    Configuré dans CELERY_BEAT_SCHEDULE pour tourner toutes les 4h (production).
    Idempotent grâce à ProactiveAlert + cooldown.
    """
    from .proactive_agent import scan_all_organizations
    return scan_all_organizations()
