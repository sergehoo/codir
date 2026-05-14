"""Moteur RBAC : résolution + cache des permissions par user × organization."""
from django.core.cache import cache


class PermissionEngine:
    CACHE_TTL = 60  # secondes

    @staticmethod
    def resolve_for(user, organization) -> set[str]:
        if not user or not getattr(user, "is_authenticated", False) or organization is None:
            return set()
        key = f"perms:{organization.id}:{user.id}"
        cached = cache.get(key)
        if cached is not None:
            return cached

        from apps.accounts.models import Membership

        membership = (
            Membership.unscoped.filter(user=user, organization=organization, is_active=True)
            .prefetch_related("roles__permissions__children")
            .first()
        )
        if not membership:
            cache.set(key, set(), PermissionEngine.CACHE_TTL)
            return set()

        permissions: set[str] = set()
        for role in membership.roles.all():
            for perm in role.permissions.all():
                if perm.is_macro:
                    permissions.update(c.code for c in perm.children.all())
                else:
                    permissions.add(perm.code)

        cache.set(key, permissions, PermissionEngine.CACHE_TTL)
        return permissions

    @staticmethod
    def has(user, organization, permission: str) -> bool:
        resolved = PermissionEngine.resolve_for(user, organization)
        if permission in resolved:
            return True
        # Wildcards : app:resource:* puis app:*:* puis *:*:*
        parts = permission.split(":")
        if len(parts) == 3:
            if f"{parts[0]}:{parts[1]}:*" in resolved:
                return True
            if f"{parts[0]}:*:*" in resolved:
                return True
        return "*:*:*" in resolved

    @staticmethod
    def invalidate(user, organization):
        cache.delete(f"perms:{organization.id}:{user.id}")
