"""Middleware multi-tenant : extrait l'organisation courante de la requête."""
from django.utils.deprecation import MiddlewareMixin

from core.managers.tenant import current_organization


class TenantMiddleware(MiddlewareMixin):
    """
    Résolution de tenant dans l'ordre :
    1. JWT claim `org_id`
    2. Sous-domaine `acme.codir.app`
    3. Header `X-Tenant-ID`
    """

    def process_request(self, request):
        org = (
            self._from_jwt(request)
            or self._from_subdomain(request)
            or self._from_header(request)
        )
        request.organization = org
        # Le ContextVar est posé ici pour être lu par TenantManager
        if org is not None:
            request._tenant_token = current_organization.set(org)

    def process_response(self, request, response):
        token = getattr(request, "_tenant_token", None)
        if token is not None:
            try:
                current_organization.reset(token)
            except (ValueError, LookupError):
                pass
        return response

    @staticmethod
    def _from_jwt(request):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from apps.organizations.models import Organization
        from apps.accounts.models import Membership

        try:
            header = JWTAuthentication().get_header(request)
            if not header:
                return None
            raw = JWTAuthentication().get_raw_token(header)
            if not raw:
                return None
            token = JWTAuthentication().get_validated_token(raw)
            org_id = token.get("org_id")
            if org_id:
                org = Organization.unscoped.filter(id=org_id, is_active=True).first()
                if org is not None:
                    return org
            # Fallback : pas de org_id dans le JWT → on prend la première
            # Membership active de l'user (utile pour les anciens tokens ou
            # les comptes mono-tenant).
            user_id = token.get("user_id")
            if user_id:
                m = (
                    Membership.unscoped
                    .filter(user_id=user_id, is_active=True, organization__is_active=True)
                    .select_related("organization")
                    .first()
                )
                if m is not None:
                    return m.organization
            return None
        except Exception:
            return None

    @staticmethod
    def _from_subdomain(request):
        from apps.organizations.models import Organization
        host = request.get_host().split(":")[0]
        parts = host.split(".")
        if len(parts) < 3:
            return None
        slug = parts[0]
        if slug in {"www", "api", "app"}:
            return None
        return Organization.unscoped.filter(slug=slug, is_active=True).first()

    @staticmethod
    def _from_header(request):
        from apps.organizations.models import Organization
        tid = request.headers.get("X-Tenant-ID")
        if not tid:
            return None
        return Organization.unscoped.filter(id=tid, is_active=True).first()
