# 13 — RBAC + ABAC

## 1. Posture d'autorisation

CODIR combine deux modèles **complémentaires** :

**RBAC (Role-Based Access Control)** — l'utilisateur appartient à une ou plusieurs `Membership` dans une `Organization`, et chaque membership porte un ou plusieurs `Role` dans cette organisation. Chaque rôle est composé d'un ensemble de `Permission` granulaires nommées par convention `app:resource:action`. C'est le mécanisme qui répond à *« cet utilisateur a-t-il le droit d'effectuer cette action en général ? »*.

**ABAC (Attribute-Based Access Control)** — par-dessus le RBAC, des **policies** évaluent au runtime des attributs (direction de l'utilisateur, attributs de la ressource, période courante, niveau de sensibilité, statut d'engagement…) pour filtrer ce que l'utilisateur peut **réellement** voir ou modifier. C'est le mécanisme qui répond à *« sur quel sous-ensemble de ces ressources ? »*.

L'évaluation est strictement **default-deny** : sans permission explicite, c'est non.

## 2. Convention de nommage des permissions

```
<app>:<resource>:<action>

Exemples :
  decisions:decision:view
  decisions:decision:create
  decisions:decision:update
  decisions:decision:delete
  decisions:decision:vote
  decisions:decision:approve
  decisions:decision:export

  meetings:meeting:view
  meetings:meeting:create
  meetings:meeting:start
  meetings:meeting:end

  budgets:budget:view
  budgets:budget:simulate
  budgets:spend:validate

  dashboards:executive:view
  documents:document:share
  audit_logs:entry:view
  audit_logs:export:create
  ai_engine:copilot:use
  admin:user:invite
  admin:role:edit
```

Quelques permissions composées (« macros ») mappent un ensemble :

```
codir:full_access         = meetings:* + agendas:* + decisions:* + action_plans:* + reports:codir
governance:executive      = dashboards:executive:view + kpis:executive:view + decisions:decision:view
finance:steward           = budgets:* + kpis:financial:view + reports:financial
audit:read_only           = audit_logs:*:view + reports:audit:create
```

## 3. Rôles standard fournis par défaut

Pour qu'un tenant soit opérationnel sans configuration, CODIR provisionne un set de rôles standard à la création de l'organisation. L'admin tenant peut les éditer (sauf protection) ou créer des rôles dérivés.

| Code | Nom | Description | Permissions clés |
|---|---|---|---|
| `OWNER` | Propriétaire | Premier admin, non révocable | `*:*:*` (full) |
| `TENANT_ADMIN` | Admin tenant | Gestion utilisateurs, rôles, intégrations | `admin:*`, `accounts:*`, `integrations:*` |
| `CHAIRMAN` | Président CODIR | Préside les sessions | `codir:full_access`, `decisions:decision:approve` |
| `SECRETARY` | Secrétaire général | Prépare et clôture les CODIR | `codir:full_access`, `reports:codir`, `documents:*` |
| `EXECUTIVE` | Directeur général | Vue exécutive complète | `governance:executive`, `kpis:*:view`, `risks:*:view` |
| `CFO` | DAF | Pilote budget, finance | `finance:steward`, `kpis:financial:*` |
| `CHRO` | DRH | Pilote RH | `kpis:hr:*`, `decisions:decision:view` |
| `CIO` | DSI | Pilote SI | `kpis:it:*`, `risks:cyber:*` |
| `DIRECTION_HEAD` | Directeur métier | Pilote sa direction | `decisions:decision:view` (scope ABAC), `kpis:direction:view` |
| `MEMBER` | Membre CODIR | Participe, vote | `meetings:*:view`, `decisions:decision:vote`, `documents:*:view` |
| `PMO` | PMO / Contrôle de gestion | Reporting | `dashboards:*:view`, `reports:*:create`, `kpis:*:view` |
| `AUDIT` | Auditeur interne | Lecture seule + audit | `audit:read_only`, `*:*:view` |
| `COMPLIANCE` | Compliance officer | Lecture + reporting | `audit:read_only`, `risks:compliance:*` |
| `LEGAL` | Juridique | Documents et signatures | `documents:*`, `decisions:decision:view` |
| `VIEWER` | Lecteur | Lecture restreinte | `*:*:view` (filtré ABAC) |

## 4. Modèle de données

```python
# apps/accounts/models.py (extrait — code complet dans backend/)

class Role(TenantAwareModel):
    code = models.SlugField()           # OWNER, CFO, CUSTOM_FOO
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)   # rôle standard non supprimable
    permissions = models.ManyToManyField("Permission", related_name="roles")

class Permission(models.Model):
    code = models.CharField(max_length=120, unique=True)   # decisions:decision:vote
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_macro = models.BooleanField(default=False)
    children = models.ManyToManyField("self", symmetrical=False, blank=True)

class Membership(TenantAwareModel):
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    roles = models.ManyToManyField(Role)
    directions = models.ManyToManyField("governance.Direction", blank=True)   # scope ABAC
    departments = models.ManyToManyField("governance.Department", blank=True)
    is_executive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)   # accès limité dans le temps
```

## 5. Moteur de résolution des permissions

```python
# core/permissions/engine.py
from collections.abc import Iterable
from django.core.cache import cache
from apps.accounts.models import Membership

class PermissionEngine:
    @staticmethod
    def resolve_for(user, organization) -> set[str]:
        key = f"perms:{organization.id}:{user.id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        membership = Membership.objects.filter(
            user=user, organization=organization, is_active=True
        ).prefetch_related("roles__permissions").first()
        if not membership:
            cache.set(key, set(), 30)
            return set()
        permissions = set()
        for role in membership.roles.all():
            for perm in role.permissions.all():
                if perm.is_macro:
                    permissions.update({c.code for c in perm.children.all()})
                else:
                    permissions.add(perm.code)
        cache.set(key, permissions, 60)
        return permissions

    @staticmethod
    def has(user, organization, permission: str) -> bool:
        resolved = PermissionEngine.resolve_for(user, organization)
        return permission in resolved or PermissionEngine._wildcard_match(permission, resolved)

    @staticmethod
    def _wildcard_match(perm: str, resolved: set[str]) -> bool:
        parts = perm.split(":")
        for i in range(len(parts), 0, -1):
            wildcard = ":".join(parts[:i] + ["*"] * (len(parts) - i))
            if wildcard in resolved:
                return True
        return "*:*:*" in resolved
```

Cache 60 s côté Redis. Invalidé lorsqu'une `Membership` ou un `Role` change (signal `post_save`).

## 6. DRF — intégration permissions

```python
# core/permissions/drf.py
from rest_framework.permissions import BasePermission
from .engine import PermissionEngine

class HasPermission(BasePermission):
    required_permission = None  # override per view

    def has_permission(self, request, view):
        perm = view.get_required_permission(request)
        if perm is None:
            return True
        return PermissionEngine.has(request.user, request.organization, perm)

class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.organization is not None and request.user.memberships.filter(
            organization=request.organization, is_active=True
        ).exists()
```

Sur une view :

```python
class DecisionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember, HasPermission]
    permission_map = {
        "list": "decisions:decision:view",
        "retrieve": "decisions:decision:view",
        "create": "decisions:decision:create",
        "update": "decisions:decision:update",
        "partial_update": "decisions:decision:update",
        "destroy": "decisions:decision:delete",
        "vote": "decisions:decision:vote",
        "approve": "decisions:decision:approve",
    }
    def get_required_permission(self, request):
        return self.permission_map.get(self.action)
```

## 7. ABAC — policies

Au-delà du oui/non global, les querysets sont filtrés par des **policies** déclaratives.

```python
# apps/decisions/policies.py
from core.permissions.engine import PermissionEngine

class DecisionAccessPolicy:
    """Filtre les décisions visibles par un utilisateur dans son organisation."""

    @staticmethod
    def filter_queryset(qs, user, organization):
        if PermissionEngine.has(user, organization, "decisions:decision:view_all"):
            return qs
        membership = organization.memberships.get(user=user)
        directions = list(membership.directions.values_list("id", flat=True))
        return qs.filter(
            models.Q(direction_id__in=directions)
            | models.Q(responsible=user)
            | models.Q(co_responsibles=user)
            | models.Q(meeting__codir_instance__permanent_members=user)
        ).distinct()

    @staticmethod
    def can_vote(decision, user) -> bool:
        return (
            decision.status == "open_for_vote"
            and decision.meeting.participations.filter(user=user, is_present=True).exists()
        )
```

Sur les viewsets :

```python
class DecisionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = Decision.objects.all()
        return DecisionAccessPolicy.filter_queryset(qs, self.request.user, self.request.organization)
```

## 8. Permissions documentaires (override ACL)

Les documents peuvent porter des permissions *en plus* du RBAC, via `DocumentPermission` (cf. doc 10). Politique : *most restrictive wins*. Un document confidentiel n'est visible que par les `users` / `roles` explicitement listés, même si un utilisateur a `documents:document:view` global.

## 9. Step-up authentication

Certaines actions sensibles exigent une **réauthentification MFA** dans les 5 dernières minutes, indépendamment de la session : changement de SSO, désactivation MFA tenant-wide, export massif, suppression définitive d'un dossier, modification d'un rôle système. L'API répond `403 step_up_required` avec instructions ; le client redéclenche la MFA et réessaie.

```python
# core/permissions/step_up.py
def require_mfa_step_up(request, max_age_seconds=300):
    last_mfa = request.user.last_mfa_at
    if not last_mfa or (now() - last_mfa).total_seconds() > max_age_seconds:
        raise PermissionDenied("step_up_required")
```

## 10. Délégation et procurations

Un membre CODIR peut **déléguer son droit de vote** à un autre membre pour une réunion donnée. C'est tracé dans `meetings.Participation` (`is_proxy`, `proxy_holder`). Le vote enregistré porte les deux identités (vote effectif + représenté). Limité à un seul niveau (pas de chaîne de procurations).

L'admin peut également configurer des **rôles temporaires** (`Membership.expires_at`) pour des intérimaires.

## 11. Audit des changements de permissions

Tout `assign_role`, `revoke_role`, `permission_add`, `permission_remove` génère une entrée audit log critique, notifiée à `OWNER` et `AUDIT` du tenant. Une page `Settings > Permissions > Journal` affiche l'historique avec diff lisible.

## 12. Tests

Test cases obligatoires sur tout endpoint :

- Un utilisateur sans permission reçoit `403`.
- Un utilisateur avec la permission mais d'un autre tenant reçoit `404` (jamais `403` pour éviter l'énumération).
- Un utilisateur avec `view_all` voit tout, sans `view_all` voit son scope ABAC.
- Les transitions de workflow vérifient la permission métier (`approve` requiert `decisions:decision:approve`).

Tests cross-tenant régressifs au CI (cf. doc 09 §15).

## 13. Boussole d'évolution

- **Hiérarchie de rôles** (un rôle peut hériter d'un autre) : nice-to-have, prévu v2.
- **ABAC par expression** (DSL pour exprimer des règles plus complexes) : prévu v2, langage type CEL (Common Expression Language) pour la portabilité.
- **Just-in-time access** (un user demande un accès, valide approbateur, expire automatiquement) : prévu v3 — utile pour les opérations sensibles auditables.
- **External authorization** (OPA, Cedar, SpiceDB) : option d'intégration v3 pour les Sovereign qui veulent un PDP externalisé.

---

*Suite : [14 — Workflows métiers](14_workflows_metiers.md)*
