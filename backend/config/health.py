"""Endpoints de santé — /health/ (liveness) et /health/ready/ (readiness).

Liveness  : retourne 200 si le process tourne (aucune dépendance vérifiée).
Readiness : 200 si DB + cache répondent. Utile en orchestrateur (K8s, ECS).
"""
from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse


def healthz(_request):
    """Liveness probe — process up."""
    return JsonResponse({"status": "ok"})


def ready(_request):
    """Readiness probe — DB + cache."""
    checks = {"db": False, "cache": False}
    status_code = 200

    try:
        connections["default"].cursor().execute("SELECT 1")
        checks["db"] = True
    except Exception as exc:  # noqa: BLE001
        checks["db_error"] = str(exc)[:200]
        status_code = 503

    try:
        cache.set("health:ping", "1", timeout=5)
        checks["cache"] = cache.get("health:ping") == "1"
        if not checks["cache"]:
            status_code = 503
    except Exception as exc:  # noqa: BLE001
        checks["cache_error"] = str(exc)[:200]
        status_code = 503

    return JsonResponse({"status": "ok" if status_code == 200 else "degraded", **checks},
                        status=status_code)
