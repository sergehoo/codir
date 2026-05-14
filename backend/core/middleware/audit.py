"""Middleware d'audit : pose un contexte requête utilisé par les signals d'audit."""
from contextvars import ContextVar

from django.utils.deprecation import MiddlewareMixin

audit_context: ContextVar[dict] = ContextVar("audit_context", default={})


class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        ctx = {
            "ip": self._client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "request_id": getattr(request, "request_id", ""),
        }
        audit_context.set(ctx)

    @staticmethod
    def _client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
