"""Service de journalisation centralisé."""
from django.contrib.contenttypes.models import ContentType

from core.middleware.audit import audit_context
from core.managers.tenant import current_organization

from .models import AuditAction, AuditLog


def log(
    *, action: str, target=None, actor=None, description: str = "",
    diff: dict | None = None, target_repr: str = "",
):
    org = current_organization.get()
    if org is None:
        return None
    ctx = audit_context.get() or {}
    target_type = ContentType.objects.get_for_model(target.__class__) if target is not None else None
    target_id = str(target.pk) if target is not None else ""
    return AuditLog.unscoped.create(
        organization=org, actor=actor, action=action,
        target_type=target_type, target_id=target_id,
        target_repr=target_repr or (str(target)[:300] if target else ""),
        description=description, diff_json=diff or {},
        ip=ctx.get("ip"), user_agent=ctx.get("user_agent", ""),
    )
