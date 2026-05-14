"""Permissions DRF basées sur le PermissionEngine."""
from rest_framework.permissions import BasePermission

from .engine import PermissionEngine


class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        if not getattr(request.user, "is_authenticated", False):
            return False
        if getattr(request, "organization", None) is None:
            return False
        return PermissionEngine.resolve_for(request.user, request.organization) is not None


class HasPermission(BasePermission):
    """
    Vérifie une permission RBAC déclarée par la view.

    Usage::
        class MyVS(ModelViewSet):
            permission_classes = [IsTenantMember, HasPermission]
            permission_map = {"list": "decisions:decision:view", ...}
            def get_required_permission(self, request):
                return self.permission_map.get(self.action)
    """

    def has_permission(self, request, view):
        perm = view.get_required_permission(request) if hasattr(view, "get_required_permission") else None
        if perm is None:
            return True
        return PermissionEngine.has(request.user, request.organization, perm)
