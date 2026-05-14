# 18 — Roadmap technique

## 1. Cap technique sur 24 mois

```
T0 ─── T+3 ─── T+6 ─── T+9 ─── T+12 ─── T+18 ─── T+24
Foundation     Core       Scale        Enterprise   Sovereign
```

## 2. Trimestre 1 (T0 — T+3) — Foundation

**Objectif :** poser les fondations sans dette.

- Mise en place mono-repo (turborepo), GitHub Actions, ruff/black/mypy/eslint/prettier baseline.
- Projet Django 6 + structure `config/settings/` + 23 apps stub initialisées.
- Docker Compose dev (PostgreSQL 16, Redis 7, OpenSearch 2, MinIO, Mailhog).
- Modèles core : `User`, `Organization`, `Subsidiary`, `Membership`, `Role`, `Permission`.
- TenantMiddleware + TenantManager + tests cross-tenant régressifs.
- Auth JWT + SimpleJWT + MFA TOTP + SSO OIDC (Google + Microsoft) + django-axes.
- Audit log signé chained.
- Pipeline CI: lint, tests, security scan (Trivy + Bandit), build images Docker.
- Frontend Next/Vite + Tanstack Router + Tailwind + Shadcn lib initialisée.
- Storybook frontend.
- Premier déploiement staging (Kubernetes 1 noeud).

## 3. Trimestre 2 (T+3 — T+6) — Core métier

**Objectif :** la mécanique CODIR fonctionne end-to-end.

- Apps `codir`, `meetings`, `agendas`, `decisions`, `action_plans` complètes (modèles, serializers, views, permissions, services).
- Workflow engine v1 (`apps/workflows`) + workflow `decision_lifecycle`.
- Channels WebSocket : consumer `meetings`, consumer `notifications`.
- App `documents` v1 : upload S3, versionning, OCR sync simple, signatures internes.
- App `notifications` v1 : email (SES/SendGrid) + push (FCM/APNs) + inapp WS.
- App `search` v1 : indexation OpenSearch synchrone à `post_save`.
- Frontend : layout shell, navigation, écrans Réunions + Décisions + Plans d'action.
- Mobile Flutter : scaffolding, auth + biométrie, écrans listes Réunions/Décisions.
- Tests E2E Playwright "Créer une décision et la voter".
- Backup + monitoring Prometheus de base.

## 4. Trimestre 3 (T+6 — T+9) — Intelligence

**Objectif :** rendre l'IA exploitable par tous les rôles.

- App `ai_engine` v1 : façade unifiée, adaptateurs OpenAI + Ollama, cache Redis.
- Pipeline transcription Whisper (queue dédiée Celery, worker GPU si dispo).
- Pipeline génération PV : extraction décisions/actions, rendu DOCX/PDF.
- RAG : pgvector, indexation auto des documents, recherche hybride.
- Copilote conversationnel SSE + frontend (drawer side panel).
- KPI engine + dashboards 4 personas (DG/DAF/DRH/DSI).
- Frontend dashboards avec ECharts.
- Mobile : mode réunion v1, vote, validation.
- Tests de charge premier passage (Locust → 1000 RPS sustained).

## 5. Trimestre 4 (T+9 — T+12) — Préparation v1.0

**Objectif :** durcir et lancer.

- Audit de sécurité externe (pen test).
- Documentation OpenAPI complète, portail développeur.
- SDK web + SDK Dart générés.
- DRP testé.
- 5 clients pilotes en production.
- 50+ scénarios E2E couverts.
- Doc tenant onboarding finalisée.
- Lancement officiel v1.0.

## 6. Trimestre 5-6 (T+12 — T+18) — Stabilisation et Enterprise core

- Apps `budgets` et `risks` complètes.
- App `integrations` v1 : SAP, Sage (lecture/écriture), Workday, Power BI.
- Signature électronique externe (Yousign, DocuSign).
- WhatsApp Business via Twilio.
- Performance : index optimisations, partitionnement audit_logs + kpi_snapshots, cache L1/L2 généralisé.
- Multi-région : audit du modèle, fix des chemins critiques pour ouverture EU + US Canada.
- Mobile v2 (signature, notes vocales).
- Édition Sovereign : packaging on-premise, runbooks.

## 7. Trimestre 7-8 (T+18 — T+24) — v2.0

- IA prédictive (Prophet, NeuralProphet, anomalies).
- Recommandations IA contextuelles.
- Agents IA (LangGraph) pour 2-3 cas d'usage : préparation auto CODIR, relances exécution.
- Édition Sovereign GA.
- Connecteurs additionnels (Oracle EBS, Tableau, Slack).
- Marketplace de templates.

## 8. Dette technique — gestion proactive

Règles strictes :

- **Pas de dette non documentée.** Toute concession trouve sa place dans `docs/DEBT.md` avec coût estimé et plan de remboursement.
- **Capacité dédiée** : 15 % de chaque sprint consacrés au remboursement (refactor, tests manquants, migration).
- **No mock en production** : si on commence avec un mock (provider IA, intégration ERP), on plante un ticket P1 dans le sprint suivant.
- **Code review obligatoire** : 1 reviewer min, 2 pour les zones critiques (auth, RBAC, multi-tenant, IA).
- **Mutation testing** sur les services critiques (mutmut, > 70 % de score).

## 9. Décisions techniques critiques à prendre

| Décision | Échéance | Choix initial | Risques |
|---|---|---|---|
| ORM async (DRF) | T+6 | Sync DRF en v1, async en v2 (DRF 4 / Django 6 async views) | Performance temps réel, refactor |
| Vector store | T0 | pgvector | Scalabilité au-delà de 100 M embeddings |
| LLM par défaut | T+3 | OpenAI GPT-4o, fallback Ollama | Coût, dépendance |
| Search store | T0 | OpenSearch | Coût ops vs ES Cloud |
| Storage | T0 | MinIO self-hosted (S3-compatible) | Backups, durabilité |
| Auth tokens | T0 | JWT RS256 | Révocation = blacklist Redis |
| Channels | T0 | Django Channels | Limite ~ 8k WS / worker — sharder |
| Multi-tenant model | T0 | Shared schema + tenant_id (Enterprise) / Schema-per-tenant (Sovereign) | Doubler le code de tests |
| ES Mobile | T+3 | Flutter, pas React Native | Recrutement plus rare en RN |
| Front state | T0 | Tanstack Query + Zustand | Migration future si besoin |

## 10. Plan de migration / refactor anticipé

À l'horizon v2, plusieurs refactors planifiés (sans surprise) :

- **`ai_engine` extrait en service externe** quand on dépasse 10k transcriptions/jour, pour donner GPU dédié et scaling indépendant.
- **OpenSearch → Elasticsearch managé** si l'op interne devient lourd (alternative : Algolia pour la search documentaire pure).
- **Sharding PostgreSQL** par tenant ou par région à 50+ TB de données (Citus extension ou managed Cloud SQL Spanner-like).
- **DRF async** sur les endpoints critiques (streaming IA, exports volumineux).

---

*Suite : [19 — Sprint planning](19_sprint_planning.md)*
