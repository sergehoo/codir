"""Permissions DRF partagées bêta."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


# ─── Résolution des rôles par organisation ────────────────────
#
# ⚠ Piège : `is_executive` existe sur DEUX modèles.
#
#   - `User.is_executive`       → flag global, hérité du mono-tenant.
#   - `Membership.is_executive` → rôle réel dans UNE organisation donnée.
#
# Toute l'application (libellé de rôle dans la sidebar, page Membres CODIR,
# /auth/my-memberships/, création d'utilisateur) pilote le rôle via le
# Membership. Les permissions, elles, lisaient `user.is_executive` : un
# utilisateur affiché « EXECUTIVE » dans l'interface se voyait refuser
# l'action, parce que son flag global était resté à False.
#
# On centralise ici la résolution correcte : rôle du membership dans
# l'organisation courante, le flag global ne servant plus que de
# surclassement (admin plateforme).


def is_org_executive(user, organization=None) -> bool:
    """True si `user` a le rôle Executive ou Owner dans `organization`.

    Le flag global `User.is_executive` reste accepté comme surclassement
    (compte d'administration transverse), mais il n'est plus requis.

    ⚠ `organization=None` renvoie False et non « n'importe quelle org » :
    accorder le rôle sur la base d'un membership dans une AUTRE
    organisation serait une escalade cross-tenant. Les appelants doivent
    fournir le tenant courant.

    Le résultat est mémoïsé sur l'instance `user` : ce prédicat est
    appelé une à deux fois par ligne dans les serializers de liste
    (can_modify, can_add_tasks), soit plusieurs centaines de requêtes sur
    une page de 50 éléments sans cache.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    # Surclassement global (héritage mono-tenant, encore utilisé par du seed).
    if getattr(user, "is_executive", False):
        return True
    if organization is None:
        return False

    org_id = getattr(organization, "id", organization)
    cache = getattr(user, "_org_exec_cache", None)
    if cache is None:
        cache = {}
        try:
            user._org_exec_cache = cache
        except Exception:  # noqa: BLE001 — user exotique (AnonymousUser figé)
            cache = {}
    if org_id in cache:
        return cache[org_id]

    from django.db.models import Q
    from apps.accounts.models import Membership
    result = Membership.unscoped.filter(
        Q(is_executive=True) | Q(is_owner=True),
        user=user, organization=organization, is_active=True,
    ).exists()
    cache[org_id] = result
    return result


def request_organization(request):
    """Organisation courante de la requête (posée par la middleware tenant)."""
    return getattr(request, "organization", None)


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


class IsOrganizationOwner(BasePermission):
    """Lecture pour membres ; écriture réservée aux Owner / Superuser / Staff Django.

    Utilisée pour les actions admin sensibles : créer/désactiver un utilisateur,
    réinitialiser un mot de passe, modifier une affectation.
    """

    message = "Action réservée aux administrateurs (DG / Owner) de l'organisation."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_superuser or request.user.is_staff:
            return True
        org = getattr(request, "organization", None)
        if org is None:
            return False
        from apps.accounts.models import Membership
        return Membership.unscoped.filter(
            user=request.user, organization=org, is_active=True, is_owner=True,
        ).exists()


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
        # Rôle résolu sur le membership de l'org courante (cf. is_org_executive).
        if is_org_executive(user, request_organization(request)):
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
        """Filtre de niveau vue, AVANT que l'objet ne soit chargé.

        ⚠ DRF appelle cette méthode avec `obj=None`. Refuser ici un
        utilisateur non-executive revenait à ne jamais évaluer la branche
        « owner du plan » de `has_object_permission` : le propriétaire d'un
        plan se prenait un 403 sur ses propres plans.

        On laisse donc passer tout membre authentifié sur les requêtes
        portant sur un objet précis (detail) — `has_object_permission`
        tranchera avec l'objet en main. Seule la création d'un plan
        « nu » (POST sur la collection) reste réservée aux rôles habilités.
        """
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        # Routes detail (pk présent) → on diffère à has_object_permission,
        # seul endroit où owner / créateur de décision sont connaissables.
        if getattr(view, "detail", False) or (view.kwargs or {}).get("pk"):
            return True
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
        if is_org_executive(user, request_organization(request)):
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
        """Même correctif que CanModifyActionPlan : sur une route detail,
        on diffère à `has_object_permission`, sinon assignee / co-assignee /
        owner du plan ne sont jamais évalués et se prennent un 403 sur
        leur propre tâche.
        """
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(view, "detail", False) or (view.kwargs or {}).get("pk"):
            return True
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
        if is_org_executive(user, request_organization(request)):
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

        # Staff Django et Executives du tenant ont accès total
        if is_org_executive(user, request_organization(request)):
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
