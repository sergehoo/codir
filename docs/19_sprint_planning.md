# 19 — Sprint planning

## 1. Cadence

- **Sprints de 2 semaines**, planning lundi matin, démo + rétro vendredi PM.
- **2 releases par mois** vers staging, **1 release majeure par mois** vers production.
- **Bug bash** dernier vendredi du mois.
- **Architecture review** mensuel (1 h, lead architecte + leads modules).
- **Roadmap review** trimestrielle avec produit + sales + customer success.

## 2. Equipe cible (12 mois)

| Rôle | T0-T+3 | T+3-T+6 | T+6-T+12 |
|---|---|---|---|
| Lead architecte / CTO | 1 | 1 | 1 |
| Backend (Django) | 2 | 3 | 5 |
| Frontend (React) | 1 | 2 | 3 |
| Mobile (Flutter) | 0 | 1 | 2 |
| IA / ML | 0 | 1 | 2 |
| Data / DBA | 0 | 0 | 1 |
| DevOps / SRE | 1 | 1 | 2 |
| QA | 0 | 1 | 2 |
| Designer / UX | 1 | 1 | 2 |
| Product manager | 1 | 1 | 2 |
| **Total** | **6** | **11** | **22** |

## 3. Sprint 0 (avant T0) — Setup

- Création du dépôt, branches policies, code owners.
- Setup environnements (dev local docker-compose, staging K8s, prod K8s).
- Setup CI/CD (GitHub Actions baseline).
- Onboarding produit + tech (lecture des docs 01-25 obligatoire).
- Choix outils : Linear/Jira, Slack/Discord, Notion/Confluence, Figma, Sentry, Loki+Grafana, Vault.
- Conventions de code, commit messages (Conventional Commits), branches (trunk-based development).

## 4. Sprint 1-2 — Foundation Auth & Tenant

**Capacité estimée :** 30 story points.

| Story | SP | Owner |
|---|---|---|
| Project scaffolding Django (config/, apps/, settings) | 3 | Backend lead |
| User model + AbstractUser custom + tests | 3 | Backend |
| Organization + Subsidiary models + admin | 2 | Backend |
| Membership + Role + Permission models | 3 | Backend |
| TenantMiddleware + TenantManager + tests | 5 | Backend lead |
| JWT auth (SimpleJWT) + login endpoint | 3 | Backend |
| MFA TOTP (django-otp) | 3 | Backend |
| SSO Google + Microsoft via OIDC | 5 | Backend |
| Frontend login + MFA screens | 3 | Frontend |

## 5. Sprint 3-4 — Audit, RBAC, Documents

| Story | SP | Owner |
|---|---|---|
| AuditEntry model + signal universel | 3 | Backend |
| Chaining + HMAC + tests d'intégrité | 5 | Backend lead |
| Permission Engine (resolve + cache) | 5 | Backend |
| DRF permissions classes + middleware | 3 | Backend |
| ABAC base + policies (decisions) | 3 | Backend |
| Doc upload S3 + presigned URLs | 3 | Backend |
| Doc versionning + history | 3 | Backend |
| OCR sync simple (Tesseract) | 3 | Backend |
| Frontend doc list + upload UX | 5 | Frontend |
| Frontend permissions HOC + masking | 3 | Frontend |

## 6. Sprint 5-6 — Meetings + Agendas

| Story | SP | Owner |
|---|---|---|
| Meeting + Agenda + AgendaItem models | 5 | Backend |
| Participation + Vote models | 3 | Backend |
| Meeting CRUD API + filters | 5 | Backend |
| Agenda CRUD + reorder | 3 | Backend |
| Channels consumer `MeetingConsumer` | 5 | Backend |
| Meeting list + detail Frontend | 5 | Frontend |
| Live meeting view (skeleton) | 5 | Frontend |
| Mobile meeting list + detail | 5 | Mobile |
| Notifications convocation (email + push) | 3 | Backend |

## 7. Sprint 7-8 — Décisions + Plans d'action

| Story | SP | Owner |
|---|---|---|
| Decision model + serializer | 3 | Backend |
| DecisionVote + vote_summary | 3 | Backend |
| WorkflowEngine v1 + decision_lifecycle | 8 | Backend lead |
| Transition endpoints | 3 | Backend |
| ActionPlan + ActionTask models | 5 | Backend |
| Frontend decision form + détail | 5 | Frontend |
| Frontend transitions UI generic | 5 | Frontend |
| Mobile decision detail + vote | 5 | Mobile |

## 8. Sprint 9-10 — IA: Whisper + génération PV

| Story | SP | Owner |
|---|---|---|
| AIService façade + adapter OpenAI | 5 | IA |
| Adapter Ollama local + test compat | 5 | IA |
| Whisper streaming pipeline (Celery + WS) | 8 | IA |
| Transcript + TranscriptChunk models | 3 | Backend |
| Extraction décisions + actions LLM | 5 | IA |
| Pipeline PV rendering DOCX/PDF | 5 | Backend |
| Frontend transcript live | 5 | Frontend |
| Frontend PV review + edit | 5 | Frontend |

## 9. Sprint 11-12 — Dashboards + KPI

| Story | SP | Owner |
|---|---|---|
| KPI + KPISnapshot models | 3 | Backend |
| Calculateur KPI (formules + agrégats) | 5 | Backend |
| Recalculation Celery beat | 3 | Backend |
| Dashboard + DashboardWidget models | 3 | Backend |
| Frontend dashboard DG (cockpit) | 8 | Frontend |
| Frontend dashboard DAF | 5 | Frontend |
| Frontend dashboard DRH | 5 | Frontend |
| Frontend dashboard DSI | 5 | Frontend |
| Mobile mini-cockpit | 5 | Mobile |

## 10. Sprint 13-14 — Search + Copilot

| Story | SP | Owner |
|---|---|---|
| Indexation OpenSearch (post_save signals) | 5 | Backend |
| Recherche hybride (pgvector + OpenSearch + RRF) | 5 | IA |
| Embeddings pipeline (upload → chunk → embed) | 5 | IA |
| Copilote AIConversation + AIMessage | 3 | Backend |
| SSE endpoint streaming | 5 | Backend |
| Frontend copilote drawer + chat | 8 | Frontend |
| Frontend search palette ⌘K | 5 | Frontend |

## 11. Sprint 15-16 — Notifications + Mobile push + Integrations v1

| Story | SP | Owner |
|---|---|---|
| Notification model + preferences | 3 | Backend |
| Email provider abstraction (SES/SendGrid) | 3 | Backend |
| Push FCM + APNs | 5 | Mobile + Backend |
| Inapp WS (déjà partiel) | 2 | Backend |
| Outlook calendar 2-way sync | 5 | Backend |
| Teams/Zoom link generation | 3 | Backend |
| Google Drive doc ingestion | 5 | Backend |
| Frontend notif center | 5 | Frontend |

## 12. Sprint 17-18 — Hardening + tests + sécurité

| Story | SP | Owner |
|---|---|---|
| Tests E2E Playwright (50 scénarios) | 8 | QA |
| Tests de charge Locust (1000 RPS) | 5 | DevOps |
| Audit RBAC cross-tenant | 5 | Backend lead |
| Pen test externe + fixes | 8 | Sécurité |
| RGPD : export utilisateur, suppression | 5 | Backend |
| DRP test complet | 5 | DevOps |
| Documentation OpenAPI complète | 3 | Backend |
| Portail développeur (Redoc + tutos) | 3 | DevRel/Frontend |

## 13. Sprint 19-20 — Pilotes + GA

| Story | SP | Owner |
|---|---|---|
| Onboarding 5 clients pilotes | 10 | CS + Backend |
| Migration de données pilotes | 5 | Backend |
| Formation utilisateurs | 5 | CS |
| Suivi métriques + retours | 5 | PM |
| Bug fixes prioritaires | 10 | All |
| Lancement officiel v1.0 | — | All |

## 14. Conventions Sprint

- **Definition of Ready** : story estimée, acceptance criteria écrits, dependencies résolues, design Figma si UI.
- **Definition of Done** : code mergé, tests > 80 %, doc à jour, design QA, déploiement staging vérifié, démo possible.
- **Critères de qualité** : couverture > 80 %, 0 P0/P1 ouvert, dashboards Sentry verts, perf budget respecté.

## 15. Risques sprint

- Sous-estimation de l'IA pipeline (transcription + PV) : prévoir buffer +30 %.
- Intégration M365/Google : APIs changeantes, prévoir spike technique en sprint 14.
- Onboarding pilotes : prévoir 4 semaines de bandwidth dédié (sprint 19-20).
- Recrutement : si retard > 1 mois sur un rôle, dégrader le scope plutôt que la qualité.

---

*Suite : [20 — DevOps & CI/CD](20_devops_cicd.md)*
