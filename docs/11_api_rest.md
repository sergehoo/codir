# 11 — API REST

## 1. Principes directeurs

**API-first, OpenAPI-driven.** Toutes les API sont définies par OpenAPI 3.1 généré par `drf-spectacular`. Le contrat OpenAPI est la source de vérité pour : le frontend web (types TypeScript générés via `openapi-typescript`), le mobile Flutter (types Dart via `openapi-generator-cli`), le portail développeur partenaire, et les tests de contrat.

**Versioning par préfixe d'URL.** `/api/v1/...`, `/api/v2/...`. Cohabitation autorisée jusqu'à 12 mois. Les changements majeurs (rupture) → nouvelle version. Les ajouts → version inchangée.

**REST + extensions pragmatiques.** Le style est REST classique (ressources nominales, méthodes HTTP standard, codes 2xx/4xx/5xx). On accepte des entorses pragmatiques pour les opérations métier (`POST /api/v1/decisions/{id}/transitions/approve`).

**Réponses JSON normalisées.** Toujours un objet (jamais un tableau racine) pour l'extensibilité.

```json
// Succès liste
{ "results": [...], "next": "cursor=...", "previous": null, "count_estimate": 12000 }

// Succès single
{ "id": "d_98", "title": "...", "..." }

// Erreur
{ "error": { "code": "decision.vote.deadline_passed", "message": "Le délai de vote est dépassé", "details": {...}, "request_id": "req_..." } }
```

**Pagination par curseur** (`limit=50&cursor=`), pas par offset (`page=`). Plus rapide sur grosses tables et stable face aux insertions.

**Authentification** : Bearer JWT (`Authorization: Bearer <access>`), refresh via `POST /api/v1/auth/refresh/` (cookie HttpOnly côté web).

**Idempotency** : header `Idempotency-Key: <uuid>` accepté sur tous les `POST` mutants ; le serveur stocke 24 h dans Redis le hash de la requête et son résultat.

**Rate limiting** : 1000 req/min par utilisateur, 5000 req/min par tenant, 20 req/min en anonyme. Réponse 429 + `Retry-After`.

**Tenancy** : tenant résolu par sous-domaine (`acme.codir.app`) ou par claim JWT ; jamais via query parameter.

## 2. Endpoints d'auth et de profil

```
POST   /api/v1/auth/login/              # email + password [+ optional MFA token]
POST   /api/v1/auth/mfa/                # POST MFA challenge response
POST   /api/v1/auth/refresh/            # refresh token
POST   /api/v1/auth/logout/             # blacklist refresh
GET    /api/v1/auth/sso/<provider>/     # redirect OIDC/SAML
POST   /api/v1/auth/sso/<provider>/callback/
GET    /api/v1/auth/sessions/           # liste sessions actives
DELETE /api/v1/auth/sessions/<id>/      # révoque une session

GET    /api/v1/me/                      # profil
PATCH  /api/v1/me/                      # update profil
GET    /api/v1/me/permissions/          # arbre RBAC résolu pour le client
GET    /api/v1/me/organizations/        # orgs auxquelles je suis membre (multi-tenant user)
POST   /api/v1/me/mfa/                  # enroll device
POST   /api/v1/me/password/             # change password
```

## 3. Organizations & gouvernance

```
GET    /api/v1/organizations/me/        # tenant courant
PATCH  /api/v1/organizations/me/        # update settings (admin)
GET    /api/v1/subsidiaries/
POST   /api/v1/subsidiaries/
GET    /api/v1/subsidiaries/{id}/
PATCH  /api/v1/subsidiaries/{id}/

GET    /api/v1/directions/
POST   /api/v1/directions/
GET    /api/v1/directions/{id}/
GET    /api/v1/directions/{id}/members/
GET    /api/v1/departments/
GET    /api/v1/positions/
GET    /api/v1/org-chart/               # arborescence pour affichage
```

## 4. CODIR & réunions

```
GET    /api/v1/codir-instances/
POST   /api/v1/codir-instances/

GET    /api/v1/meetings/?status=&from=&to=&codir_instance=
POST   /api/v1/meetings/
GET    /api/v1/meetings/{id}/
PATCH  /api/v1/meetings/{id}/
DELETE /api/v1/meetings/{id}/

POST   /api/v1/meetings/{id}/transitions/start/         # démarre la réunion
POST   /api/v1/meetings/{id}/transitions/end/
POST   /api/v1/meetings/{id}/transitions/cancel/

GET    /api/v1/meetings/{id}/participants/
POST   /api/v1/meetings/{id}/participants/              # invite
PATCH  /api/v1/meetings/{id}/participants/{user_id}/    # statut RSVP
POST   /api/v1/meetings/{id}/check-in/                  # arrivée

GET    /api/v1/meetings/{id}/agenda/
PATCH  /api/v1/meetings/{id}/agenda/                    # met à jour ordre + items
POST   /api/v1/meetings/{id}/agenda/items/
PATCH  /api/v1/meetings/{id}/agenda/items/{item_id}/
DELETE /api/v1/meetings/{id}/agenda/items/{item_id}/
POST   /api/v1/meetings/{id}/agenda/generate-ai/        # IA propose un ordre du jour

GET    /api/v1/meetings/{id}/transcript/                # transcript fini
GET    /api/v1/meetings/{id}/minutes/                   # PV
POST   /api/v1/meetings/{id}/minutes/generate/          # déclenche génération IA
GET    /api/v1/meetings/{id}/minutes/draft/             # brouillon en cours
POST   /api/v1/meetings/{id}/minutes/finalize/          # validation + signature

POST   /api/v1/meetings/{id}/votes/                     # cast vote (pendant la séance)
GET    /api/v1/meetings/{id}/votes/                     # bilan agrégé
```

## 5. Décisions & plans d'action

```
GET    /api/v1/decisions/?status=&direction=&priority=&deadline_before=
POST   /api/v1/decisions/
GET    /api/v1/decisions/{id}/
PATCH  /api/v1/decisions/{id}/
DELETE /api/v1/decisions/{id}/

POST   /api/v1/decisions/{id}/transitions/{name}/       # vote_open, approve, start, complete, cancel
POST   /api/v1/decisions/{id}/votes/                    # cast async (cas vote-par-écrit)
GET    /api/v1/decisions/{id}/history/
GET    /api/v1/decisions/{id}/timeline/                 # vue chrono

GET    /api/v1/decisions/{id}/action-plan/
POST   /api/v1/decisions/{id}/action-plan/              # crée
PATCH  /api/v1/decisions/{id}/action-plan/

GET    /api/v1/action-plans/{id}/tasks/
POST   /api/v1/action-plans/{id}/tasks/
PATCH  /api/v1/tasks/{id}/                              # raccourci pour task
POST   /api/v1/tasks/{id}/transitions/{name}/           # start, review, complete, block
POST   /api/v1/tasks/{id}/evidence/                     # upload preuve d'exécution
```

## 6. KPI, dashboards, budgets, risques

```
GET    /api/v1/dashboards/
POST   /api/v1/dashboards/
GET    /api/v1/dashboards/{id}/
PATCH  /api/v1/dashboards/{id}/
POST   /api/v1/dashboards/{id}/widgets/
PATCH  /api/v1/dashboards/{id}/widgets/{wid}/
DELETE /api/v1/dashboards/{id}/widgets/{wid}/

GET    /api/v1/kpis/?category=&direction=&owner=
POST   /api/v1/kpis/
GET    /api/v1/kpis/{id}/
GET    /api/v1/kpis/{id}/snapshots/?from=&to=&interval=day
GET    /api/v1/kpis/{id}/forecast/?horizon=12&algo=prophet

GET    /api/v1/budgets/?year=&entity=
POST   /api/v1/budgets/
GET    /api/v1/budgets/{id}/lines/
POST   /api/v1/budgets/{id}/lines/
POST   /api/v1/budgets/{id}/scenarios/
POST   /api/v1/budget-lines/{id}/spend/                 # imputation dépense

GET    /api/v1/risks/?status=&category=&severity_min=
POST   /api/v1/risks/
GET    /api/v1/risks/{id}/
POST   /api/v1/risks/{id}/assessments/
GET    /api/v1/risks/heatmap/                           # matrice (impact x prob)
GET    /api/v1/incidents/
POST   /api/v1/incidents/
```

## 7. Documents & rapports

```
GET    /api/v1/documents/?folder=&type=&q=
POST   /api/v1/documents/                              # multipart upload
GET    /api/v1/documents/{id}/
GET    /api/v1/documents/{id}/versions/
POST   /api/v1/documents/{id}/versions/                # nouvelle version
GET    /api/v1/documents/{id}/download/                # presigned URL S3
POST   /api/v1/documents/{id}/ocr/                     # déclenche OCR
POST   /api/v1/documents/{id}/sign/                    # workflow signature
GET    /api/v1/documents/{id}/annotations/
POST   /api/v1/documents/{id}/annotations/

GET    /api/v1/reports/templates/
POST   /api/v1/reports/runs/                           # crée un run
GET    /api/v1/reports/runs/{id}/                      # statut/résultat
POST   /api/v1/reports/scheduled/                      # cron
```

## 8. IA — copilot, recherche, génération

```
POST   /api/v1/ai/copilot/conversations/               # nouvelle conv
GET    /api/v1/ai/copilot/conversations/{id}/
POST   /api/v1/ai/copilot/conversations/{id}/messages/ # streaming SSE
GET    /api/v1/ai/copilot/conversations/{id}/messages/stream  # SSE pull

POST   /api/v1/ai/summarize/                           # texte → résumé
POST   /api/v1/ai/extract-decisions/                   # texte → décisions JSON
POST   /api/v1/ai/transcribe/                          # audio → transcript (async)

POST   /api/v1/search/                                 # recherche sémantique hybride
GET    /api/v1/search/suggestions/?q=

POST   /api/v1/ai/risk-detect/                         # scan documents → risques
POST   /api/v1/ai/anomaly-detect/                      # KPI → anomalies
```

## 9. Notifications & intégrations

```
GET    /api/v1/notifications/?unread=true
PATCH  /api/v1/notifications/{id}/                     # marquer lue / agir
POST   /api/v1/notifications/mark-all-read/

GET    /api/v1/notifications/preferences/
PATCH  /api/v1/notifications/preferences/

GET    /api/v1/integrations/
POST   /api/v1/integrations/                           # configure (OAuth flow)
DELETE /api/v1/integrations/{id}/
POST   /api/v1/integrations/{id}/sync/                 # déclenche sync manuelle
GET    /api/v1/integrations/{id}/runs/

POST   /api/v1/webhooks/                               # outgoing
GET    /api/v1/webhooks/{id}/deliveries/
```

## 10. Audit & administration

```
GET    /api/v1/audit/entries/?actor=&action=&target_type=&from=&to=
GET    /api/v1/audit/entries/{id}/
POST   /api/v1/audit/exports/                          # CSV signé / PDF horodaté

GET    /api/v1/admin/users/                            # admin tenant
POST   /api/v1/admin/users/                            # invite
PATCH  /api/v1/admin/users/{id}/
DELETE /api/v1/admin/users/{id}/                       # désactive

GET    /api/v1/admin/roles/
POST   /api/v1/admin/roles/
PATCH  /api/v1/admin/roles/{id}/                       # update permissions

GET    /api/v1/admin/feature-flags/
PATCH  /api/v1/admin/feature-flags/{key}/
GET    /api/v1/admin/health/                           # status modules
```

## 11. API mobile (différences)

L'app mobile consomme l'API v1 standard, **plus** les endpoints `/api/v1/mobile/*` optimisés :

```
POST   /api/v1/mobile/sync/delta?since=<cursor>&types=meetings,decisions,notifications
       → payload compact (champs réduits, IDs courts)
POST   /api/v1/mobile/devices/                         # enroll device push (FCM/APNs token)
POST   /api/v1/mobile/notes-vocales/                   # audio → speech-to-text
GET    /api/v1/mobile/feed/today/                      # mini-cockpit du jour
```

## 12. Conventions de filtre, tri, recherche

```
?status=in_progress,blocked       # multiple values comma-separated
?priority=high                    # exact
?created_at__gte=2026-01-01       # range
?title__icontains=phoenix         # search
?ordering=-deadline,title         # tri multiple
?expand=responsible,direction     # inlining de sous-ressources contrôlé
?fields=id,title,deadline         # sparse fieldsets
?lang=fr                          # locale override
```

## 13. Codes d'erreur métier (extraits)

```
auth.invalid_credentials
auth.mfa_required
auth.mfa_invalid
auth.session_revoked
auth.password_expired

permission.denied
permission.tenant_mismatch

decisions.vote.deadline_passed
decisions.vote.already_cast
decisions.transition.invalid_state

meetings.quorum_not_reached
meetings.cant_start_yet
meetings.transcript_unavailable

ai.provider_unavailable
ai.token_budget_exceeded
ai.guardrails_violation

documents.virus_detected
documents.size_limit_exceeded

rate_limit.exceeded
idempotency.key_reuse_conflict
validation.invalid_input
```

Chaque code est documenté dans le portail OpenAPI avec exemples.

## 14. Exemple complet — créer une décision

```http
POST /api/v1/decisions/ HTTP/1.1
Host: acme.codir.app
Authorization: Bearer eyJ...
Content-Type: application/json
Idempotency-Key: 9c8a7f6e-1234-4567-8901-abcdef012345
X-Request-ID: req_01HXG5Y6...

{
  "meeting": "m_42",
  "agenda_item": "ai_087",
  "title": "Lancement projet Phoenix",
  "summary_md": "Investissement de 4,2 M€ pour moderniser le SI client.",
  "category": "dc_invest",
  "priority": "critical",
  "impact": "strategic",
  "budget_amount": 4200000,
  "budget_currency": "EUR",
  "budget_line": "bl_2026_si_invest",
  "direction": "dir_dsi",
  "responsible": "u_dsi_head",
  "deadline": "2026-12-31",
  "risks": ["rsk_2026_0034"],
  "kpis": ["kpi_satis_si"]
}
```

```http
HTTP/1.1 201 Created
Location: /api/v1/decisions/d_98
Content-Type: application/json

{
  "id": "d_98",
  "ref": "DEC-2026-0042",
  "status": "proposed",
  "created_at": "2026-05-13T09:14:23Z",
  "created_by": {"id":"u_sg","name":"Catherine Martin"},
  "vote_summary": {"yes":0,"no":0,"abstain":0,"pending":12},
  "transitions_available": ["open_vote","cancel"],
  ...
}
```

## 15. Découvrabilité

- `GET /api/v1/openapi.json` (schéma OpenAPI 3.1)
- `GET /docs/api/` (Redoc / Swagger UI)
- `GET /api/v1/_health/` (liveness)
- `GET /api/v1/_ready/` (readiness, dépendances DB, Redis, ES)
- `GET /metrics` (Prometheus, scope interne)

## 16. Stratégie de breaking changes

Annonce 6 mois avant retrait d'une version. Header `Deprecation` + `Sunset` poussé sur tous les endpoints d'une version dépréciée 3 mois avant. Outillage SDK : régénération automatique des SDK web/mobile à chaque release OpenAPI.

---

*Suite : [12 — WebSocket](12_websocket.md)*
