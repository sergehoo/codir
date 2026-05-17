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


class CanModifyActionPlan(BasePermission):
    """Permission de modifier/supprimer un Plan d'action.

    Règles :
      - Lecture (SAFE_METHODS) : tous les membres de l'org
      - Modification/Suppression : staff, executive, ou créateur/owner du plan
      - Sinon : 403

    Pour modifier la liste des autorisés, ajouter des rôles via Membership
    et étendre la condition ici.
    """

    message = "Vous n'avez pas la permission de modifier ce plan d'action."

    def _user_can_modify(self, request, obj=None) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "is_executive", False):
            return True
        if obj is not None:
            # Owner du plan
            if getattr(obj, "owner_id", None) == user.id:
                return True
            # Créateur de la décision liée
            decision = getattr(obj, "decision", None)
            if decision and getattr(decision, "created_by_id", None) == user.id:
                return True
        return False

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # Pour les méthodes write (create) : staff/exec uniquement
        return self._user_can_modify(request)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return self._user_can_modify(request, obj)


class CanModifyTask(BasePermission):
    """Permission de modifier/supprimer une ActionTask.

    Règles :
      - Lecture : tous les membres de l'org
      - Modification/Suppression :
          * staff Django
          * is_executive (membre COMEX)
          * assignee principal de la tâche
          * co_assignee (collaborateur additionnel)
          * owner du plan d'action parent
          * créateur de la décision liée
      - Sinon : 403
    """

    message = "Vous n'avez pas la permission de modifier cette tâche."

    def _user_can_modify(self, request, obj=None) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "is_executive", False):
            return True
        if obj is None:
            return False
        # Assignee principal → peut tout faire sur sa propre tâche
        if getattr(obj, "assignee_id", None) == user.id:
            return True
        # Co-assignee → peut aussi modifier (équipier)
        try:
            if obj.co_assignees.filter(id=user.id).exists():
                return True
        except (AttributeError, Exception):  # noqa: BLE001 — graceful si M2M pas migré
            pass
        # Owner du plan d'action parent
        plan = getattr(obj, "action_plan", None)
        if plan and getattr(plan, "owner_id", None) == user.id:
            return True
        # Créateur de la décision parente
        decision = getattr(plan, "decision", None) if plan else None
        if decision and getattr(decision, "created_by_id", None) == user.id:
            return True
        return False

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # Pour les méthodes write (create) : staff/exec uniquement
        return self._user_can_modify(request)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return self._user_can_modify(request, obj)


class CanModifyOwnComment(BasePermission):
    """Permission éditer/supprimer un commentaire.

    Règles :
      - Lecture : tous les membres de l'org
      - Modification/Suppression : auteur uniquement, ou staff/executive
    """

    message = "Vous ne pouvez modifier que vos propres commentaires."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "is_executive", False):
            return True
        return getattr(obj, "author_id", None) == user.id


class CanModifyTaskInSubsidiary(BasePermission):
    """⚠ Permission DÉSACTIVÉE par défaut.

    Conserve la logique de cloisonnement par filiale pour un usage futur
    éventuel (sous-tenants, rôles "manager de filiale", etc.).
    Pour CODIR Kaydan : tous les membres voient et modifient tout.

    Pour réactiver : ajouter `CanModifyTaskInSubsidiary` à
    `ActionTaskViewSet.permission_classes` dans `action_plans/views.py`.

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
