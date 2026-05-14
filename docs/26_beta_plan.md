# 26 — Plan de livraison bêta CODIR

## 1. Périmètre verrouillé

Cœur métier : `meetings`, `agendas`, `decisions`, `action_plans`.
Support : `common`, `accounts`, `organizations`, `governance` (minimal), `documents`, `notifications`, `audit_logs`, `dashboards`.

Hors périmètre bêta : `budgets`, `risks`, `analytics`, `ai_engine`, `realtime` (WebSocket), `kpis`, `reports` avancés, `workflows` génériques, `integrations`, `search`. Les modèles existent dans le repo mais sont retirés d'`INSTALLED_APPS`.

## 2. Workflow utilisateur cible (parcours complet)

```
Auth (login JWT)
  ↓
Dashboard bêta
  ↓
Création réunion (DRAFT)
  ↓ Ajout participants (chair + secretary auto-ajoutés)
  ↓ Création agenda + items
  ↓ Validation agenda → réunion passe à SCHEDULED
  ↓ Notifications email envoyées
  ↓
Jour J : start_meeting → IN_PROGRESS
  ↓ Présence enregistrée par secrétaire
  ↓ Discussion item par item (status = discussed)
  ↓ Création décision depuis item agenda
  ↓
Clôture : complete_meeting → COMPLETED + PV HTML auto-généré
  ↓
Validation décision (approve)
  ↓ Conversion en plan d'action
  ↓ Création tâches + assignation
  ↓ Tâches notifiées aux assignés (email + inapp)
  ↓
Suivi : update_progress / complete_task
  ↓ Celery beat détecte les retards → notif + status = overdue
  ↓
Tout est audité dans `audit_logs.AuditLog`.
```

## 3. Plan sprints (4 × 2 semaines)

### Sprint 1 — Foundation auth + meetings (2 semaines)

| Story | Estimation |
|---|---|
| Project setup (settings beta, urls, .env, docker-compose) | 0,5 j |
| User custom + Membership + login JWT + endpoint /me/ | 1 j |
| Organization minimal + TenantMiddleware | 0,5 j |
| Modèle `Meeting` + serializers + ViewSet + filtres | 1,5 j |
| `MeetingParticipant` + endpoints participants | 1 j |
| `MeetingAttendance` + endpoint attendance + transitions | 1 j |
| Services `create_meeting`, `schedule`, `cancel` | 1 j |
| Tests unitaires meetings (smoke + transitions) | 1 j |
| Frontend : layout + login + dashboard skeleton | 1,5 j |
| Frontend : MeetingsListPage + MeetingCreatePage + MeetingDetailPage | 1,5 j |

**Critères :** créer une réunion, ajouter des participants, voir la réunion sur le dashboard.

### Sprint 2 — Agendas + workflow réunion

| Story | Estimation |
|---|---|
| Modèles Agenda + AgendaItem + AgendaItemComment | 1 j |
| Services validate_agenda, reorder, discuss_item, postpone_item | 1 j |
| Endpoints agenda + items + transitions | 1 j |
| start_meeting / complete_meeting + génération PV HTML | 1 j |
| Signaux audit + notification (invitation, validation, démarrage) | 0,5 j |
| Frontend : page agenda inline dans MeetingDetail | 1,5 j |
| Frontend : mode réunion simple (transitions, discussion items) | 1,5 j |
| Tests agendas + transitions complete_meeting | 1 j |

**Critères :** créer agenda, valider, tenir une réunion avec changements de statut, générer un PV HTML.

### Sprint 3 — Décisions + plans d'action

| Story | Estimation |
|---|---|
| Modèles Decision + DecisionHistory + DecisionComment + auto-ref | 1 j |
| Services approve/start/complete/cancel/postpone | 1 j |
| Endpoint convert-to-action-plan + tasks bulk-creation | 1 j |
| Modèles ActionPlan + ActionTask + ActionComment + ActionEvidence | 1 j |
| Services update_progress / complete_task / recompute progress plan | 1 j |
| Endpoints decisions + action-plans + my-decisions + my-tasks | 1 j |
| Frontend : DecisionsListPage + DecisionDetailPage (transitions) | 1,5 j |
| Frontend : ActionPlansListPage + ActionPlanDetailPage + MyTasksPage | 1,5 j |
| Tests workflow décision → plan d'action | 1 j |

**Critères :** créer décision depuis item agenda, valider, convertir en plan, créer tâches, mettre à jour avancement.

### Sprint 4 — Dashboard, notifications, audit, stabilisation

| Story | Estimation |
|---|---|
| Endpoint /dashboard/beta/ consolidé | 0,5 j |
| Service centralisé notifications + email Celery | 1 j |
| Tâches Celery detect_overdue + send_meeting_reminders + send_deadline_reminders | 1 j |
| Service audit_logs.log + intégration via signaux | 1 j |
| Modèle Document + DocumentAttachment + upload S3/MinIO | 1 j |
| Frontend : DashboardPage + NotificationsPage + indicateur unread topbar | 1 j |
| Frontend : composant AttachmentUploader (réutilisable) | 1 j |
| Seed data + management commands | 0,5 j |
| Tests d'intégration end-to-end (Playwright sur 3 scénarios clés) | 1,5 j |
| Documentation OpenAPI + portail Swagger | 0,5 j |
| Bug bash + retours pilotes | 1,5 j |

**Critères :** dashboard fonctionnel, notifications email reçues, retards détectés automatiquement, audit log alimenté.

## 4. Migrations à créer (ordre)

```
1. organizations    (Organization, Subsidiary)
2. accounts         (User, Membership, Role, Permission)
3. governance       (Direction, Department, Position) — bêta minimal
4. common           (pas de tables, juste init)
5. documents        (Document, DocumentAttachment)
6. meetings         (Meeting, MeetingParticipant, MeetingAttendance, MeetingNote, MeetingMinutes)
7. agendas          (Agenda, AgendaItem, AgendaItemComment)
8. decisions        (Decision, DecisionCategory, DecisionHistory, DecisionComment)
9. action_plans     (ActionPlan, ActionTask, ActionComment, ActionEvidence)
10. notifications   (Notification)
11. audit_logs      (AuditLog)
12. dashboards      (vide pour bêta, juste l'app)
```

Génération :

```bash
python manage.py makemigrations organizations accounts governance common documents \
    meetings agendas decisions action_plans notifications audit_logs dashboards
python manage.py migrate
```

## 5. Seed bêta — données initiales

Le management command `python manage.py seed_beta` doit créer :

- 1 `Organization` (« Acme Corp ») + 1 `Subsidiary` (« Acme France »)
- 1 `Direction` (« DG ») + 1 (« DAF ») + 1 (« DSI »)
- 5 utilisateurs (admin, dg, daf, secrétaire, employé) + memberships
- 5 rôles standards (OWNER, CHAIRMAN, SECRETARY, EXECUTIVE, MEMBER)
- 2 réunions d'exemple (1 scheduled, 1 completed avec décisions + tâches)
- 3 décisions à différents statuts
- 1 plan d'action complet avec tâches assignées + 1 tâche en retard
- 5 notifications variées (read et unread)
- 10 entrées d'audit log

## 6. Tests prioritaires (couverture cible 80%)

### Backend

```
tests/test_meetings.py
  - test_create_meeting_auto_adds_chair_and_secretary_as_participants
  - test_start_meeting_requires_validated_agenda
  - test_complete_meeting_generates_minutes
  - test_complete_meeting_checks_quorum
  - test_completed_meeting_cannot_be_modified (423)
  - test_cancel_meeting_logs_reason

tests/test_agendas.py
  - test_validate_empty_agenda_returns_409
  - test_validate_agenda_publishes_meeting_to_scheduled
  - test_reorder_items
  - test_locked_agenda_rejects_new_items

tests/test_decisions.py
  - test_create_decision_assigns_auto_ref
  - test_approve_proposed_decision
  - test_cannot_start_unapproved_decision
  - test_decision_history_records_transitions
  - test_my_decisions_filters_responsible
  - test_convert_to_action_plan_creates_plan_and_tasks
  - test_cannot_convert_unapproved_decision

tests/test_action_plans.py
  - test_create_task_under_plan
  - test_update_progress_changes_status
  - test_completing_all_tasks_marks_plan_completed
  - test_overdue_detection_marks_status_and_notifies

tests/test_dashboard.py
  - test_beta_dashboard_returns_user_specific_metrics

tests/test_permissions.py
  - test_non_member_cannot_access_meetings (403)
  - test_member_of_org_a_cannot_read_org_b_data
```

### Frontend

```
src/features/meetings/__tests__/MeetingCreatePage.test.tsx
  - validates required fields
  - submits and navigates to detail

src/features/decisions/__tests__/DecisionDetailPage.test.tsx
  - shows approve button only in proposed state
  - convert-to-action-plan navigates to plan
```

## 7. Critères d'acceptation bêta — checklist

- [ ] Connexion JWT fonctionnelle (login + refresh + /me)
- [ ] Tenant isolation testée et validée (cross-tenant impossible)
- [ ] Création réunion → ajout participants → notification email envoyée
- [ ] Préparation ordre du jour → ajout items → validation
- [ ] Démarrage réunion (uniquement si agenda validé)
- [ ] Présence enregistrée
- [ ] Création décision depuis item agenda
- [ ] Décision en historique trace les transitions
- [ ] Conversion décision → plan d'action + tâches
- [ ] Assignation de tâche déclenche notification email + inapp
- [ ] Mise à jour avancement → recalcul du plan
- [ ] Clôture meeting → PV HTML disponible
- [ ] Detect overdue (Celery beat) marque les tâches retard
- [ ] Notifications listées + marquage lu
- [ ] Dashboard bêta affiche 9 KPI + prochaines réunions + dernières notifs
- [ ] Audit log alimenté pour create / update / approved / validated / cancelled
- [ ] Tests backend > 80 %
- [ ] OpenAPI Swagger consultable sur `/docs/api/`

## 8. Commandes-clés pour démarrer la bêta

```bash
# Backend
cd backend
cp .env.example .env
docker compose up -d postgres redis minio mailhog
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_beta
python manage.py runserver
# Workers
celery -A config worker -Q default,notifications -l info
celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler

# Frontend
cd frontend/web
pnpm install
pnpm dev
```

## 9. Workflow démo CODIR de référence

> *À montrer aux pilotes en 8 minutes.*

1. Login `dg@acme.local` / `Codir!2026`.
2. Dashboard : on voit 2 réunions à venir, 3 décisions en attente, 5 tâches.
3. **Créer réunion** "Revue trimestrielle T2" → date + lieu + chair + secretary.
4. **Ajouter 3 participants** (DAF, DRH, DSI).
5. **Créer agenda** + 3 items (priorité haute, moyenne, basse).
6. **Valider l'agenda** → la réunion passe à SCHEDULED. Notification email envoyée aux participants.
7. **Démarrer la réunion** → IN_PROGRESS.
8. **Marquer présence** : 3 présents / 1 absent.
9. **Discuter item 1** + notes → status discussed.
10. **Créer décision** depuis l'item : titre, priorité critique, responsable DAF, échéance 30 jours.
11. **Approuver la décision** → notification au DAF.
12. **Convertir en plan d'action** + 3 tâches.
13. **Clôturer la réunion** → PV HTML généré automatiquement.
14. Le DAF se connecte, voit la décision et les tâches dans **Mes tâches**, met à jour avancement.
15. Demain matin Celery détecte que la tâche dont l'échéance est passée → status `overdue` + notif au DAF.

## 10. Risques bêta identifiés

| Risque | Mitigation |
|---|---|
| Volumétrie utilisateurs initiale faible — Celery beat non testé | Smoke test scénario overdue avec date manuelle |
| Upload S3/MinIO sur premier déploiement on-prem | Fallback FileSystemStorage docker |
| Auth multi-tenant : sous-domaine vs JWT — confusion | Imposer header `X-Tenant-ID` en dev |
| PV HTML brut peu esthétique pour démo client | Template CSS d'export PDF prévu sprint 4 |
| Notifications mail bloquées par filtres | Tester sur 3 fournisseurs (Gmail, Outlook 365, ProtonMail) avant pilote |

## 11. Sortie de bêta — conditions

1. 3 organisations pilotes actives ≥ 30 jours
2. > 50 réunions tenues sur la plateforme
3. > 100 décisions tracées avec plans d'action
4. NPS pilote ≥ 30
5. 0 incident P0/P1 sur les 14 derniers jours
6. Taux de génération PV satisfaisant ≥ 90 %

Ces conditions remplies → bascule en GA v1.0 (cf. `docs/17_roadmap_produit.md`).
