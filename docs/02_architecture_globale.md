# 02 — Architecture globale

## 1. Principes architecturaux directeurs

L'architecture de CODIR repose sur sept principes non négociables qui guident chaque décision technique.

**API-first.** Toute fonctionnalité est exposée par une API REST DRF (ou WebSocket pour le temps réel) avant d'être consommée par un front. Le web, le mobile et les intégrations externes sont des clients de premier rang équivalents.

**Event-driven.** Les actions métier produisent des événements (`decision.created`, `meeting.started`, `kpi.threshold.breached`) propagés via Celery + Redis pour les tâches asynchrones et via Django Channels + Redis pub/sub pour le temps réel. Aucun couplage synchrone entre apps métier.

**Multi-tenant par défaut.** Chaque requête s'inscrit dans un contexte `Organization` injecté par middleware. Toutes les tables métier portent une FK `organization_id` indexée et toutes les requêtes ORM passent par un manager `TenantManager` qui filtre automatiquement.

**Zero-trust.** Authentification systématique (JWT court), autorisation contextuelle (RBAC + ABAC), chiffrement en transit (TLS 1.3) et au repos (AES-256 pour les fichiers, `pgcrypto` pour les champs sensibles), audit de chaque mutation.

**Audit-by-design.** Toutes les actions critiques (décision créée, vote enregistré, document supprimé, permission modifiée) sont consignées dans une table `audit_logs.AuditEntry` immutable, signée et exportable.

**AI-as-a-service interne.** Le module `ai_engine` est isolé derrière une API stable : changer de modèle (OpenAI → Ollama → Claude) ne touche aucune autre app. Le RAG est centralisé.

**Cloud-agnostic & on-prem capable.** Stack 100 % conteneurisée Docker, déployable sur Kubernetes, AWS ECS, ou bare-metal souverain. Aucun service managé propriétaire bloquant.

## 2. Vue d'ensemble en un schéma

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                    │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Web React/TS  │  │ Mobile Flutter│  │ Intégrations tierces   │   │
│  │ Shadcn + Tan  │  │ iOS + Android │  │ SAP/Sage/Power BI/Teams │   │
│  └──────┬────────┘  └──────┬───────┘  └──────────┬──────────────┘   │
└─────────┼──────────────────┼─────────────────────┼──────────────────┘
          │ HTTPS/WSS        │ HTTPS/WSS           │ HTTPS/Webhooks
          ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│              EDGE — Traefik (TLS, rate-limit, WAF)                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        ▼                         ▼                             ▼
┌───────────────────┐   ┌───────────────────┐         ┌─────────────────┐
│ API HTTP (Django  │   │ ASGI Channels     │         │ Webhook gateway │
│ + DRF + Gunicorn) │   │ (WebSockets)      │         │ (FastAPI)       │
└────────┬──────────┘   └────────┬──────────┘         └────────┬────────┘
         │                       │                             │
         └───────────────┬───────┴─────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────┐
        │   COUCHE MÉTIER — 23 apps Django    │
        │                                     │
        │  accounts · organizations · gov.    │
        │  codir · meetings · agendas         │
        │  decisions · action_plans · wf      │
        │  dashboards · kpis · budgets        │
        │  risks · reports · analytics        │
        │  ai_engine · realtime · notif.      │
        │  documents · search · integrations  │
        │  audit_logs · mobile_api · admin    │
        └────────┬────────────────────┬───────┘
                 │                    │
                 ▼                    ▼
       ┌───────────────────┐   ┌────────────────────┐
       │ Celery workers    │   │ AI workers         │
       │ (broker Redis)    │   │ (Ollama/OpenAI)    │
       │ - notifications   │   │ - transcription    │
       │ - reports         │   │ - résumé           │
       │ - OCR             │   │ - embeddings       │
       │ - sync ERP        │   │ - RAG              │
       └─────────┬─────────┘   └──────────┬─────────┘
                 │                        │
                 └────────────┬───────────┘
                              ▼
   ┌──────────────────────────────────────────────────────┐
   │              COUCHE DONNÉES & PERSISTANCE            │
   │                                                      │
   │  PostgreSQL 16     Redis 7        OpenSearch         │
   │  (OLTP + pgvector) (cache,        (search full-text  │
   │                     queue, ws)     + analytics)      │
   │                                                      │
   │  MinIO/S3                ClickHouse (analytics OLAP) │
   │  (documents, fichiers)   (optionnel pour scale)      │
   └──────────────────────────────────────────────────────┘
```

## 3. Style architectural

CODIR adopte un **monolithe modulaire** (modular monolith) plutôt qu'une microservicearchitecture. Ce choix est délibéré et porte trois justifications :

D'abord, **les 23 modules sont fortement couplés sémantiquement** : une décision référence une réunion, qui référence un ordre du jour, qui peut produire un plan d'action, qui alimente un KPI. Casser cette cohésion en services distribués ajouterait du transactionnel distribué sans bénéfice. Ensuite, **la transactionnalité forte** (un vote enregistré doit créer la décision et l'engagement en une seule transaction) est triviale dans un monolithe et complexe en microservices. Enfin, **l'équipe de départ** (5-10 ingénieurs) ne peut pas opérer 23 services indépendants.

Le découpage en **apps Django** garantit la modularité interne : chaque app a ses modèles, ses serializers, ses views, ses permissions, ses tests. Les apps communiquent par services Python (jamais par accès direct aux modèles d'une autre app au-delà de FKs). Quand un module atteint une charge ou une criticité justifiant l'extraction (par exemple `ai_engine` si on monte à 10 000 transcriptions/jour, ou `search` si OpenSearch devient le goulot), il pourra être extrait en service indépendant sans réécriture.

À côté du monolithe vivent **deux services adjacents** : un `webhook-gateway` en FastAPI (pour absorber les pics de webhooks ERP avec une faible empreinte mémoire), et les **workers Celery** dans deux pools séparés (default + IA, le pool IA ayant accès aux GPU si présents).

## 4. Cartographie des apps Django

Les 23 apps Django sont regroupées en **6 domaines fonctionnels** pour clarifier les responsabilités.

**Domaine 1 — Identité & Tenant (foundation).** `accounts` (utilisateurs, profils, MFA, sessions), `organizations` (tenant racine, filiales, structure), `governance` (organigrammes, directions, postes, hiérarchie), `administration` (paramétrage tenant, branding, modules activés).

**Domaine 2 — Gouvernance & Réunions (cœur métier CODIR).** `codir` (instance de CODIR, statut, cycle), `meetings` (sessions, convocations, présence, votes), `agendas` (ordres du jour, sujets, priorisation), `decisions` (décisions prises, statut, suivi), `action_plans` (plans d'action issus des décisions), `workflows` (machines d'état génériques pour validation).

**Domaine 3 — Pilotage & Mesure (analytics).** `dashboards` (configuration et persistance des dashboards), `kpis` (définition, calcul, historique), `budgets` (budgets, dépenses, scénarios), `risks` (cartographie, scoring, incidents), `reports` (génération PDF/Word/Excel/PPT), `analytics` (cubes OLAP, agrégations, forecasting).

**Domaine 4 — Intelligence & Temps réel.** `ai_engine` (LLM, RAG, transcription, résumé, recommandations), `realtime` (présence, édition collaborative, broadcast WS), `notifications` (email/SMS/push/WhatsApp), `search` (indexation OpenSearch, recherche sémantique).

**Domaine 5 — Contenu & Documents.** `documents` (upload, versioning, OCR, signature), `integrations` (connecteurs SAP, Odoo, M365, Power BI, Teams, etc.).

**Domaine 6 — Observabilité & Mobile.** `audit_logs` (journalisation immutable), `mobile_api` (endpoints optimisés Flutter, formats compacts, sync delta).

Le détail de chaque app est dans [`docs/03_architecture_backend.md`](03_architecture_backend.md) et les modèles complets dans [`docs/10_modeles_donnees.md`](10_modeles_donnees.md).

## 5. Flux de données critiques

### 5.1. Tenir un CODIR — flow nominal

```
1. Secrétaire général crée la session  ─►  meetings.Meeting
2. Génération assistée de l'ordre du jour ─► agendas.Agenda + ai_engine
3. Convocations + pièces jointes        ─►  notifications + documents
4. Réunion live (visio + transcription) ─►  realtime (WS) + ai_engine (STT)
5. Votes, décisions, engagements        ─►  meetings.Vote, decisions.Decision
6. Génération du PV par IA              ─►  ai_engine + reports
7. Diffusion + signature                ─►  notifications + documents
8. Plans d'action générés               ─►  action_plans + workflows
9. Suivi exécution & relances           ─►  Celery beat + notifications
10. KPI consolidation & dashboard       ─►  analytics + kpis + dashboards
```

Ce flux engage 12 apps simultanément. La cohérence est assurée par les transactions PostgreSQL pour les écritures critiques (votes, décisions) et par des événements Celery pour le reste (notifications, génération de rapports, indexation search).

### 5.2. Décision → Plan d'action — workflow d'engagement

Une décision CODIR n'est jamais en cul-de-sac : sa création déclenche automatiquement un workflow `decision_to_action`. Ce workflow propose au porteur de la décision un template de plan d'action (à partir du module `workflows`), assigne les responsables, fixe les jalons, et programme les relances. L'IA suggère le template le plus approprié en se basant sur la catégorie de la décision et l'historique. Chaque tâche du plan d'action remonte son avancement vers un KPI agrégé `taux_execution_decisions_codir` exposé sur le dashboard DG.

### 5.3. KPI breach → alerte exécutive

Le module `kpis` recalcule chaque KPI selon une fréquence définie (temps réel, horaire, quotidienne). Si la valeur franchit un seuil défini, un événement `kpi.threshold.breached` est publié. Le module `notifications` consomme l'événement, identifie les destinataires (DG + porteur du KPI), génère une notification multi-canal et la pousse en temps réel via WebSocket sur le cockpit ouvert du DG. Le module `ai_engine` est appelé en parallèle pour générer une analyse de cause racine probable à partir du contexte (autres KPI, décisions liées, événements récents).

## 6. Patterns techniques transverses

**Service layer.** Entre les views DRF et les modèles, on intercale une couche `services/` par app (`apps/decisions/services.py`) qui encapsule la logique métier. Les views restent fines (parsing, autorisation, sérialisation). Les services sont appelables depuis les tasks Celery, depuis le shell admin, depuis les commandes de management.

**Domain events.** Le module `realtime` expose une fonction `publish_event(channel, event_type, payload)` qui combine la persistance (si pertinente), le pub/sub Redis pour les WS, et la mise en file Celery pour les conséquences asynchrones. Tous les modules métier publient des événements plutôt que d'appeler directement les autres modules.

**Outbox pattern.** Pour les événements qui doivent absolument être délivrés (notification de décision critique, webhook vers SAP), on écrit dans une table `outbox_events` dans la même transaction que l'écriture métier. Un worker Celery dépile la table et délivre, garantissant l'at-least-once.

**Caching multi-niveau.** Cache L1 process (LRU pour les permissions résolues, lifecycle requête), cache L2 Redis (objets fréquents avec TTL court : organigramme, configuration tenant), cache L3 CDN pour les statics et les documents publics.

**Idempotency keys.** Toutes les mutations critiques exposent un header `Idempotency-Key`. Le serveur stocke 24 h dans Redis le hash de la requête et son résultat. Un client mobile qui réessaie après timeout ne crée jamais de doublon.

## 7. Topologie de déploiement de référence

```
┌─ Tier Production (zone privée) ─────────────────────────────────┐
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────┐      │
│  │ Traefik  │───►│ App pods x N │    │ Worker pods x M    │      │
│  │ (2 repl) │    │ (Django/ASGI)│    │ (Celery default+ai)│      │
│  └──────────┘    └──────┬───────┘    └──────────┬─────────┘      │
│                         │                       │                │
│                         └───────────┬───────────┘                │
│                                     │                            │
│         ┌─────────────┬─────────────┼─────────────┐              │
│         ▼             ▼             ▼             ▼              │
│   ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌──────────┐         │
│   │PostgreSQL│  │  Redis    │  │MinIO/S3 │  │OpenSearch│         │
│   │ primary  │  │ cluster   │  │         │  │          │         │
│   │ + replica│  │ (3 nodes) │  │         │  │          │         │
│   └──────────┘  └───────────┘  └─────────┘  └──────────┘         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
   ▲
   │ VPN / private link
┌──┴────────────────────────────────────────────────────────────────┐
│  Tier IA (zone GPU optionnelle pour Ollama on-prem)               │
│                                                                   │
│   Ollama GPU pod x K (Llama 3, Mixtral, Whisper)                  │
│   Redis (vector cache)                                            │
└───────────────────────────────────────────────────────────────────┘
```

## 8. Choix structurants justifiés

| Choix | Alternative écartée | Justification |
|---|---|---|
| Monolithe modulaire | Microservices | Couplage métier fort, équipe initiale réduite |
| PostgreSQL + pgvector | Pinecone / Weaviate | Une seule DB, transactionnel unifié, coût opérationnel |
| Django Channels (ASGI) | Socket.IO séparé | Authentification et permissions héritées de Django |
| Celery + Redis | RabbitMQ, Kafka | Stack standard Django, ops connus, suffisant à 10k jobs/min |
| OpenSearch | Elasticsearch | Licence Apache, pas de risque Elastic |
| Ollama + OpenAI | OpenAI seul | Souveraineté pour clients régulés, on-prem possible |
| Flutter | React Native | UI native, perf, écosystème offline-first plus mûr |
| Traefik | Nginx | Auto-discovery Docker, certificats Let's Encrypt natifs |

## 9. Limites et risques architecturaux assumés

L'approche monolithe modulaire implique qu'**un bug bloquant dans une app peut affecter toute la plateforme**. C'est mitigé par : tests unitaires et d'intégration > 80 %, déploiements progressifs (canary), feature flags par module activable au tenant.

Le **multi-tenant logique** (et non physique) implique qu'une faille de sécurité dans un filtre tenant pourrait exposer des données croisées. C'est mitigé par : audit automatisé via un middleware `TenantContextEnforcer` qui lève une exception si un queryset traverse les frontières tenant, tests de pénétration trimestriels, mode "physical isolation" en édition Sovereign (base PG dédiée par tenant via schémas PG).

La **latence IA** (transcription Whisper, génération PV) peut dégrader l'UX en réunion live. Mitigé par : streaming WebSocket, modèles plus légers en première passe puis modèle premium en revue, file dédiée GPU, batching intelligent.

## 10. Boussole d'évolution

L'architecture est conçue pour évoluer sans rupture :

D'abord, **l'extraction de services** se fait module par module quand la charge le justifie. Le candidat n°1 est `ai_engine` (GPU, charges asymétriques). Candidat n°2 : `search` (OpenSearch tend à devenir un produit en soi). Candidat n°3 : `notifications` (multi-canal complexe).

Ensuite, **le passage à Kubernetes** est trivial puisque tout est containerisé. Le Helm chart est fourni dès la v1.

Enfin, **le multi-région** sera supporté en v2 via le pattern *region-local read replica + global write primary* pour PostgreSQL, et un déploiement par région pour les workers et la couche API, avec routage géo via Traefik.

---

*Suite : [03 — Architecture backend](03_architecture_backend.md)*
