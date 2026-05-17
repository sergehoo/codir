"""Permissions DRF partagées bêta."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOrganizationMember(BasePermission):
    """Empêche tout accès si l'utilisateur n'appartient pas au tenant courant."""

    message = "Vous n'êtes pas membre de cette organisation."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        if org is None:
            return False
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=request.user, organization=org, is_active=True
        ).exists()


class IsOwnerOrReadOnly(BasePermission):
    """L'objet doit avoir un champ `created_by` / `owner` / `responsible` pour SAFE; sinon owner only."""

    owner_fields = ("created_by", "owner", "responsible", "assignee", "user")

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        for f in self.owner_fields:
            if hasattr(obj, f) and getattr(obj, f) == request.user:
                return True
        return False


class IsAdminOrReadOnly(BasePermission):
    """Lecture pour tous les membres, écriture pour staff/admin tenant."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, "is_executive", False)
        ))


class CanModifyMeeting(BasePermission):
    """Une réunion terminée est verrouillée sauf pour staff."""

    message = "La réunion est verrouillée car terminée ou annulée."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.status not in {"completed", "cancelled"}


def _task_subsidiary_id(task):
    """Résout la filiale d'une tâche via : task → action_plan → decision → direction → subsidiary.

    Renvoie None si la chaîne est rompue (tâche orpheline ou direction sans filiale).
    """
    plan = getattr(task, "action_plan", None)
    decision = getattr(plan, "decision", None) if plan else None
    direction = getattr(decision, "direction", None) if decision else None
    return getattr(direction, "subsidiary_id", None) if direction else None


class CanModifyTaskInSubsidiary(BasePermission):
    """Cloisonnement filiale : un user ne peut modifier que les tâches de SA filiale.

    Règles :
      - Lecture (SAFE_METHODS) : autorisée à tous les membres de l'org
      - Staff/Executive : pass — peut tout modifier (vue exec consolidée)
      - User dans 1+ filiales : peut modifier les tâches dont la filiale ∈ ses filiales
      - User sans filiale (rôle Groupe) : pass — vue transverse
      - User assigné à la tâche : pass — sa propre tâche
      - Sinon : 403
    """

    message = (
        "Cette tâche appartient à une autre filiale. "
        "Vous ne pouvez modifier que les tâches de votre périmètre."
    )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Staff Django et users `is_executive` du tenant ont accès total
        if user.is_staff or getattr(user, "is_executive", False):
            return True

        # Si la tâche est assignée à l'utilisateur, il peut toujours la modifier
        if getattr(obj, "assignee_id", None) == user.id:
            return True

        org = getattr(request, "organization", None)
        if org is None:
            return False

        user_subs = user.subsidiary_ids_for(org)

        # User transverse Groupe (aucune filiale assignée) → accès complet à l'org
        if not user_subs:
            return True

        # Sinon : la filiale de la tâche doit être dans les filiales du user
        task_sub = _task_subsidiary_id(obj)
        if task_sub is None:
            # Tâche sans filiale rattachée (ex: rattachée au Groupe) → autorisé
            return True
        return task_sub in user_subs
