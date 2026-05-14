# 09 — Architecture multi-tenant

## 1. Modèles d'isolation et choix retenus

Trois modèles d'isolation existent en SaaS multi-tenant :

**A — Database-per-tenant** : une base PostgreSQL par tenant. Isolation maximale, coûts d'exploitation exponentiels, complique les migrations, pénalise les requêtes cross-tenant (admin, analytics).

**B — Schema-per-tenant** (PostgreSQL schemas) : un schéma par tenant dans la même base. Isolation forte, opérations groupées, mais migrations à exécuter N fois, et la limite PG (~2 000 schémas par cluster) plafonne le scaling.

**C — Shared schema avec discriminant** : une seule base, un seul schéma, chaque ligne porte un `organization_id`. Scalable à 100 000+ tenants, migrations triviales, requêtes cross-tenant simples, mais l'isolation dépend rigoureusement de filtres applicatifs corrects.

**CODIR retient le modèle C par défaut pour les éditions Essential et Enterprise**, et **bascule sur le modèle B (schema-per-tenant) pour Sovereign** quand le client exige une isolation forte attestable.

L'architecture est conçue pour que **le code applicatif soit identique** dans les deux cas — seule la configuration change (un *tenant resolver* différent).

## 2. Modèle de données — la pyramide tenant

```
       ┌─────────────────────────┐
       │      Organization       │  ← tenant racine
       │  (Acme Bank, Min. Santé) │
       └───────────┬─────────────┘
                   │ 1—n
       ┌───────────▼─────────────┐
       │       Subsidiary        │  ← filiales / entités
       │ (Acme Côte d'Ivoire …)  │
       └───────────┬─────────────┘
                   │ 1—n
       ┌───────────▼─────────────┐
       │       Direction         │  ← directions
       │ (DAF, DRH, DSI …)       │
       └───────────┬─────────────┘
                   │ 1—n
       ┌───────────▼─────────────┐
       │       Department        │
       │ (Trésorerie, Recrut. …) │
       └─────────────────────────┘
```

L'**Organization** est le tenant primitif. Les **Subsidiary**, **Direction**, **Department** sont des sous-structures hiérarchiques *internes* au tenant. Toutes les tables métier portent une FK directe vers `organization_id` (pour le filtrage tenant) et peuvent porter des FKs additionnelles vers `subsidiary_id`, `direction_id`, etc. (pour les permissions fines ABAC).

## 3. TenantMiddleware — résolution du tenant courant

```python
# core/middleware/tenant.py
from contextvars import ContextVar
from django.utils.deprecation import MiddlewareMixin
from apps.organizations.models import Organization

current_organization: ContextVar = ContextVar("current_organization", default=None)

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        org = (
            self._from_jwt(request)
            or self._from_subdomain(request)
            or self._from_header(request)
        )
        if org is None and request.path.startswith("/api/"):
            from rest_framework.exceptions import NotAuthenticated
            raise NotAuthenticated("Tenant context missing")
        request.organization = org
        current_organization.set(org)

    def _from_jwt(self, request):
        token = self._extract_jwt(request)
        if not token:
            return None
        org_id = token.get("org_id")
        return Organization.objects.filter(id=org_id, is_active=True).first()

    def _from_subdomain(self, request):
        host = request.get_host()
        sub = host.split(".")[0]
        return Organization.objects.filter(slug=sub, is_active=True).first()

    def _from_header(self, request):
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return None
        return Organization.objects.filter(id=tenant_id, is_active=True).first()
```

Le `ContextVar` permet à n'importe quel code (manager, signal, task Celery via `bind_current_tenant`) d'accéder au tenant courant sans le passer en paramètre partout.

## 4. TenantManager — filtrage automatique

```python
# core/managers/tenant.py
from django.db import models
from core.middleware.tenant import current_organization

class TenantQuerySet(models.QuerySet):
    def for_current_tenant(self):
        org = current_organization.get()
        if org is None:
            raise RuntimeError("No tenant in context; refusing to leak data")
        return self.filter(organization_id=org.id)

class TenantManager(models.Manager):
    def get_queryset(self):
        org = current_organization.get()
        qs = TenantQuerySet(self.model, using=self._db)
        if org is None:
            # Mode "unscoped" volontaire seulement via .unscoped
            return qs.none()
        return qs.filter(organization_id=org.id)
```

Sur les modèles tenant :

```python
class Decision(TenantAwareModel):
    objects = TenantManager()            # filtre auto
    unscoped = models.Manager()          # accès admin/migrations
```

Si un développeur tente d'utiliser `Decision.objects.all()` sans tenant en contexte, il obtient un `RuntimeError` clair — la défense en profondeur préfère un crash bruyant à une fuite silencieuse.

## 5. TenantAwareModel — la base abstraite

```python
# core/models/base.py
import uuid
from django.db import models
from core.managers.tenant import TenantManager

class TimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class TenantAwareModel(TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )
    objects = TenantManager()
    unscoped = models.Manager()
    class Meta:
        abstract = True
        indexes = [models.Index(fields=["organization", "-created_at"])]
```

Tous les modèles métier héritent de `TenantAwareModel`. Le `Meta.indexes` garantit l'index composite organization+date qui répond aux requêtes paginées par défaut.

## 6. Isolation au niveau Celery

Les tâches Celery doivent transporter le tenant explicitement (les ContextVars ne traversent pas les frontières processus) :

```python
# core/celery/tenant_task.py
from celery import Task
from core.middleware.tenant import current_organization
from apps.organizations.models import Organization

class TenantTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        tenant_id = kwargs.pop("__tenant_id__", None)
        if tenant_id:
            org = Organization.objects.unscoped.get(id=tenant_id)
            current_organization.set(org)
        try:
            return self.run(*args, **kwargs)
        finally:
            current_organization.set(None)

# Usage
@app.task(base=TenantTask)
def recalculate_kpis(kpi_id):
    ...

# Appel
recalculate_kpis.apply_async(args=[kpi_id], kwargs={"__tenant_id__": str(org.id)})
```

Une commande helper `tenant_task.delay_for(org, *args, **kwargs)` cache cette mécanique.

## 7. Isolation au niveau Channels (WebSocket)

Le `JWTAuthMiddleware` pose `scope["organization"]` au connect. Tous les groupes Channel sont nommés en incluant l'organisation :

```python
self.group_name = f"org.{org.id}.meeting.{meeting_id}"
```

Une connexion ne peut pas s'abonner à un groupe d'un autre tenant — la jonction est calculée serveur-side à partir du scope, jamais du payload client.

## 8. Stockage objet multi-tenant

Sur MinIO/S3, deux options évaluées et choix retenu :

- **A — Buckets séparés par tenant** : un bucket par tenant, ACL strict. Bon pour audit, surcoût d'administration sur 10 000+ tenants.
- **B — Bucket commun avec préfixe `tenant/<org_id>/`** : un seul bucket, préfixe imposé par middleware, policies IAM/MinIO interdisant le cross-prefix.

CODIR adopte **B par défaut** (simplicité, scaling), avec option **A en édition Sovereign**. Le client de stockage est wrappé :

```python
class TenantScopedStorage:
    def _key(self, path: str) -> str:
        org = current_organization.get()
        if org is None:
            raise RuntimeError("No tenant for storage operation")
        return f"tenant/{org.id}/{path}"
```

## 9. Cache Redis multi-tenant

Toutes les clés cache sont préfixées par le tenant via un wrapper `cache.set(tenant_key("dashboards:dg:summary"), value)`. Les invalidations cross-key sont scopées tenant. Aucune clé ne traverse les tenants.

## 10. Recherche OpenSearch multi-tenant

Deux niveaux d'isolation OpenSearch sont évalués :

- **Index par tenant** (`docs-org-<id>`) : isolation forte, mappings indépendants, mais 23 apps × N tenants = explosion d'index.
- **Index commun avec champ `tenant_id` + filter sur chaque requête** : performance optimale, isolation logique, attention à ne jamais oublier le filtre.

CODIR retient **l'index commun avec routing** (`?routing=<tenant_id>`) pour bénéficier de la co-localisation des shards par tenant, et un wrapper `TenantOpenSearchClient` qui ajoute systématiquement le filter `term: {tenant_id: <id>}`. Index séparés en Sovereign.

## 11. Sovereign — schema-per-tenant

Pour les éditions Sovereign, on bascule vers **schema-per-tenant** sans changer le code :

- Un `TenantSchemaRouter` Django modifie dynamiquement `search_path` PG en fonction du tenant courant.
- Les migrations sont exécutées par un management command `manage.py migrate_all_tenants` qui itère sur les schémas.
- Le filtre `organization_id` reste mais devient redondant (tous les rows du schéma sont du même tenant).

Cette bascule est invisible côté applicatif et garantit l'évolution sans refactor.

## 12. Provisioning / déprovisioning d'un tenant

**Provisioning** : `manage.py tenant_provision --org-name "Acme Bank" --plan enterprise --region eu-west`. La commande crée l'`Organization`, configure les modules activés, génère les buckets/préfixes, configure le SSO si paramétré, importe les templates par défaut (catégories de décision, organigramme blank), génère les credentials admin initial, envoie l'email de bienvenue.

**Déprovisioning** : conformité RGPD. Suspension immédiate (`is_active=False` filtre tout). Période de grâce 30 j (récupération possible). Suppression effective : purge des données via `manage.py tenant_purge --org-id <id> --confirm`. Export final fourni au client (ZIP chiffré). Audit log conservé séparément 5 ans.

## 13. Migration entre éditions

Un client Essential peut migrer vers Enterprise (activation de nouveaux modules) sans interruption. Un Enterprise vers Sovereign exige une migration de données : export depuis le shared schema → import dans un schéma dédié → bascule de la configuration tenant. Outillage `manage.py tenant_migrate_to_sovereign --org-id <id>` automatise les 6 étapes (export, dump, restore, settings flip, smoke test, cutover).

## 14. Observabilité par tenant

Toutes les métriques Prometheus et tous les logs Loki sont *labellisés* par `organization_id` (limité aux top 1000 tenants en labels, le reste en attribut log). Les dashboards Grafana proposent un sélecteur tenant pour le support et les SRE. La facturation à l'usage (sur la roadmap v2) consomme ces métriques.

## 15. Tests dédiés multi-tenant

Une test class `MultiTenantTestCase` instancie systématiquement deux tenants A et B, crée des entités dans chacun, et vérifie qu'aucune fonction de l'API ne renvoie de données du tenant B quand on est authentifié sur A. Ces tests sont régressifs : tout endpoint nouveau doit être couvert. Ils sont en CI et bloquants.

## 16. Limites et garde-fous

- L'oubli du `TenantAwareModel` sur un modèle métier est attrapé par un check `manage.py check --deploy` custom qui scanne les apps et lève une erreur si un modèle dans `LOCAL_APPS` n'hérite pas ou n'a pas explicitement été marqué `@global_model`.
- L'ouverture d'une connexion DB hors contexte tenant lève une exception en production.
- Une requête SQL brute (`raw()`, `cursor.execute()`) doit obligatoirement passer par un helper `tenant_raw(sql, params, tenant=None)` qui injecte le filtre.

---

*Suite : [10 — Modèles de données](10_modeles_donnees.md)*
