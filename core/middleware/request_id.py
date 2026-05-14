"""Génère / propage un X-Request-ID."""
import uuid

from django.utils.deprecation import MiddlewareMixin


class RequestIdMiddleware(MiddlewareMixin):
    HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"

    def process_request(self, request):
        request.request_id = request.META.get(self.HEADER) or f"req_{uuid.uuid4().hex[:24]}"

    def process_response(self, request, response):
        response[self.RESPONSE_HEADER] = getattr(request, "request_id", "")
        return response
