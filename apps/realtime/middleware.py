"""Middleware Channels : extrait l'auth JWT depuis la query string."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model

User = get_user_model()


@database_sync_to_async
def _get_user_and_org(jti_or_token):
    """Stub : à compléter avec validation SimpleJWT + lookup Organization."""
    from rest_framework_simplejwt.tokens import UntypedToken
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from apps.organizations.models import Organization

    try:
        token = UntypedToken(jti_or_token)
    except (InvalidToken, TokenError):
        return None, None
    user_id = token.get("user_id")
    org_id = token.get("org_id")
    user = User.objects.filter(id=user_id).first()
    org = Organization.unscoped.filter(id=org_id, is_active=True).first() if org_id else None
    return user, org


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        qs = parse_qs((scope.get("query_string") or b"").decode())
        token = (qs.get("token") or [None])[0]
        scope["user"] = None
        scope["organization"] = None
        if token:
            user, org = await _get_user_and_org(token)
            scope["user"] = user
            scope["organization"] = org
        return await super().__call__(scope, receive, send)
