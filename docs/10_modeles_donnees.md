# 10 — Modèles de données

> Le code Django **exécutable** est dans `backend/apps/<app>/models.py`. Ce document décrit l'architecture des données, les relations et les choix de modélisation. Pour chaque app, il liste les modèles principaux et leurs invariants.

## 1. Conventions globales

**Clés primaires** : UUID v4 pour tous les modèles métier (collision impossible, prédictibilité nulle, multi-région friendly). Les modèles purement techniques (tables de jointure simples) peuvent rester en BigInteger.

**Timestamps** : `created_at`, `updated_at` partout via `TimestampedModel`. `deleted_at` pour soft-delete sur les entités principales (décisions, plans d'action, documents, KPI).

**Tenant** : tous les modèles métier héritent de `TenantAwareModel` (cf. doc 09). FK `organization` indexée, contrainte d'intégrité forte.

**Index composites** privilégiés : presque toutes les requêtes scopées tenant + filtrage temporel ; chaque modèle pose `Index(fields=["organization", "-created_at"])` minimum.

**Audit** : chaque modèle critique active `AuditMixin` qui branche `post_save`/`post_delete` vers `audit_logs.AuditEntry`.

**Statuts** : par convention, statuts en `TextChoices` Django + machine d'état explicite dans `apps/workflows/states.py` quand non trivial.

**Soft delete** : `is_deleted: bool + deleted_at: datetime`. Managers respectent par défaut le flag (`active = TenantManager(exclude_deleted=True)`).

## 2. Cartographie globale des relations

```
Organization ──┬── Subsidiary ──── Direction ──── Department ──── Position
               │
               ├── User (M2M via Membership) ──── Role ──── Permission
               │
               ├── CodirInstance ──── Meeting ──── Agenda ──┬── AgendaItem
               │                                            └── Attachment
               │                                ├── Participation
               │                                ├── Vote
               │                                ├── MeetingNote
               │                                └── Transcript
               │
               ├── Decision ──┬── DecisionVote
               │              ├── DecisionAttachment
               │              ├── DecisionHistory
               │              └── ActionPlan ──── ActionTask ──── ActionSubtask
               │
               ├── KPI ──── KPISnapshot ──── KPIAlert
               ├── Dashboard ──── DashboardWidget
               │
               ├── Budget ──── BudgetLine ──── BudgetSpend
               ├── Risk ──── RiskAssessment ──── RiskMitigation ──── Incident
               │
               ├── Document ──── DocumentVersion ──── DocumentAnnotation
               ├── Report
               │
               ├── Notification ──── NotificationChannel ──── NotificationDelivery
               ├── Integration ──── IntegrationCredential ──── IntegrationSyncRun
               │
               ├── AIInferenceLog ──── AIDocumentEmbedding
               ├── AuditEntry (chained, signed)
               └── Workflow ──── WorkflowState ──── WorkflowTransition
```

## 3. App `accounts`

`User` étend `AbstractUser` Django :
- `id` UUID
- `email` unique (auth principale)
- `phone_e164`, `locale`, `timezone`
- `mfa_enabled`, `mfa_method` (TOTP/WebAuthn/Push)
- `last_login_ip`, `last_login_geo`
- `must_change_password`
- `is_executive` (raccourci pour les hooks)

`MFADevice` : type, payload chiffré (secret TOTP, credential WebAuthn), `last_used_at`.

`Session` : token JWT id, IP, user-agent, geo MaxMind, device fingerprint, `revoked_at`.

`PasswordHistory` : pour empêcher la réutilisation des 5 derniers mots de passe.

`InvitationToken` : invitation par email pour rejoindre une `Organization`.

## 4. App `organizations`

`Organization` (tenant racine) :
- `name`, `slug`, `legal_form`, `siret`, `vat_number`
- `logo`, `primary_color`, `secondary_color` (branding)
- `country`, `timezone`, `currency`
- `plan` (essential/enterprise/sovereign), `is_active`
- `sso_enforced`, `sso_provider_id`
- `data_residency`, `ai_config` (FK `administration.AIConfiguration`)

`Subsidiary` : filiales d'une `Organization` ; mêmes informations légales.

`Membership` : table de jointure `User × Organization` avec attributs : `is_owner`, `is_executive`, `roles` (M2M), `directions` (M2M), `joined_at`, `invited_by`.

## 5. App `governance`

Représentation de la structure interne du tenant.

`Direction` : direction fonctionnelle (DAF, DRH, DSI…), FK `Organization` ou `Subsidiary`, FK `head` (User, directeur).

`Department` : département sous une direction, FK `Direction`, FK `head`.

`Position` : poste — `title`, `level` (C-level, VP, Director, Manager, IC), FK `Department`, FK `holder` (User), `is_executive_committee_member`.

`OrgChartNode` : nœud arborescent pour rendu d'organigramme (FK self-parent + ordre + collapsed state UI), `governable` (GenericForeignKey vers Direction/Department/Position).

## 6. App `codir`

`CodirInstance` représente la structure formelle du Comité de Direction d'une `Organization` ou d'une `Subsidiary` :
- `name` (« CODIR Groupe », « CODIR France »)
- `frequency` (weekly/bi-weekly/monthly)
- `default_day_of_week`, `default_time`
- `default_duration_minutes`
- `quorum_min_members`
- `chairperson` (FK User)
- `secretary` (FK User)
- `permanent_members` (M2M User)

`CodirCharter` (charte CODIR) : règles, votes, secret/non secret, durée des mandats — rendu Markdown pour version PDF.

## 7. App `meetings`

`Meeting` :
- FK `codir_instance`
- `title`, `description`, `meeting_type` (regular/extraordinary/strategic)
- `scheduled_start`, `scheduled_end`, `actual_start`, `actual_end`
- `location` (physique), `video_url` (Teams/Zoom/Meet), `meeting_password`
- `status` (draft/scheduled/in_progress/completed/cancelled)
- `chair` (FK User), `secretary` (FK User)
- `quorum_reached: bool`, `recording_url`, `transcript_url`
- `agenda` (OneToOne `agendas.Agenda`)
- `minutes_doc` (FK `documents.Document`)

`Participation` : `Meeting × User` avec `role` (member/invited/observer), `response` (accepted/declined/tentative), `is_present`, `joined_at`, `left_at`.

`Vote` : vote nominatif sur un sujet ou une décision.
- FK `meeting`, FK `target` (GenericFK vers `Decision` ou `AgendaItem`)
- FK `voter` (User)
- `choice` (yes/no/abstain), `weight` (pour conseils pondérés), `is_proxy`, `proxy_holder`
- `cast_at`

`MeetingNote` : notes collaboratives (Yjs binary blob + version), scope (item ou meeting-wide), visibilité (public/personal).

`Transcript` : `chunks` (table fille) issus de la transcription IA.

`TranscriptChunk` : `start_ts`, `end_ts`, `speaker`, `text`, `confidence`.

## 8. App `agendas`

`Agenda` : OneToOne avec `Meeting`. `is_locked` (figé à T-24 h).

`AgendaItem` :
- FK `agenda`
- `order` (int)
- `title`, `description_md`, `category` (FK)
- `priority` (low/medium/high/critical)
- `estimated_duration_minutes`, `actual_duration_minutes`
- `presenter` (FK User), `direction` (FK), `linked_decision_template` (FK option)
- `expected_outcome` (info/decision/vote)
- `status` (planned/in_progress/done/postponed/cancelled)
- `discussion_summary` (rempli par IA)
- `attachments` (M2M `documents.Document`)

`AgendaItemCategory` : taxonomy par tenant (« Stratégie », « Finance », « RH », « Risque »…), color tag.

## 9. App `decisions`

`Decision` :
- `ref` (auto, `DEC-2026-0042`)
- `title`, `summary_md`, `full_text_md`
- FK `meeting`, FK `agenda_item` (option), FK `direction`
- `category` (FK `DecisionCategory`)
- `priority` (low/medium/high/critical), `impact` (low/medium/high/strategic)
- `budget_amount`, `budget_currency`, FK `budget_line` (option)
- `responsible` (FK User), `co_responsibles` (M2M)
- `deadline`, `started_at`, `completed_at`
- `status` (proposed/voted/approved/in_progress/completed/cancelled/blocked)
- `risks` (M2M `risks.Risk`)
- `kpis` (M2M `kpis.KPI`)
- `vote_summary` (JSON snapshot)
- `parent_decision` (FK self pour décisions liées)

`DecisionCategory` : (« Investissement », « Stratégie », « Réorganisation »…).

`DecisionHistory` : audit interne dédié (mutations détaillées humanly readable).

`DecisionVote` : vote nominatif (M2M résolu — agrégation des `Vote` de meetings).

`DecisionAttachment` : pièces complémentaires post-vote (preuves d'exécution, contrats signés…).

## 10. App `action_plans`

`ActionPlan` : un plan déclenché par une décision.
- FK `decision`, `title`, `description_md`
- `start_date`, `target_end_date`, `actual_end_date`
- `status`, `progress_percent` (calculé)
- FK `owner` (User)

`ActionTask` :
- FK `action_plan`, FK `parent` (self, optionnel pour sous-tâche)
- `title`, `description_md`, `priority`, `status` (todo/in_progress/review/done/blocked)
- FK `assignee`, `co_assignees` M2M
- `due_date`, `started_at`, `completed_at`
- `effort_estimate_hours`, `effort_actual_hours`
- `dependencies` (M2M self)
- `tags` (M2M)
- `is_milestone: bool`

`ActionEvidence` : preuves d'exécution attachées à une tâche/décision (document, lien externe).

## 11. App `workflows`

Moteur de machine d'état générique pour valider des entités (décisions, plans d'action, budgets, dépenses, signatures de PV).

`WorkflowDefinition` : template (JSON DAG), `applies_to` (ContentType).

`WorkflowInstance` : instance attachée à une entité, FK `definition`, FK `target`, `current_state`.

`WorkflowTransition` : log des transitions (`from_state`, `to_state`, `actor`, `comment`, `at`).

`Approval` : tâche d'approbation requise dans un état (`approver`, `due_at`, `status`).

## 12. App `dashboards` et `kpis`

`Dashboard` :
- FK `owner` (User), `is_template`, `is_shared`
- `name`, `description`, `layout_json` (gridstack layout)
- `target_persona` (DG/DAF/DRH/DSI/PMO/Custom)

`DashboardWidget` :
- FK `dashboard`
- `widget_type` (kpi_card/line_chart/bar_chart/heatmap/radar/table/text)
- `config_json` (data source, filtres, palette)
- `position_json` (x,y,w,h)

`KPI` :
- `code` (unique tenant), `name`, `description`, `category` (financial/hr/ops/it/risk/quality)
- `unit` (€, %, count, days, score)
- `target_value`, `target_direction` (max/min/range)
- `warning_threshold`, `critical_threshold`
- `frequency` (real_time/hourly/daily/weekly/monthly)
- `formula` (DSL custom) ou `source_integration` (FK)
- `owner` (FK User), `consumers` (M2M Direction)

`KPISnapshot` : valeur ponctuelle. `kpi`, `value`, `period_start`, `period_end`, `breakdown_json` (subsidiary, direction). Partitionné par mois pour grosse volumétrie.

`KPIAlert` : déclenchement de seuil. `kpi`, `snapshot`, `level` (warning/critical), `message`, `resolved_at`.

## 13. App `budgets`

`Budget` : année + entité + monnaie + statut.

`BudgetLine` : ligne budgétaire — `name`, `category`, `direction`, `planned_amount`, `committed_amount`, `spent_amount`, `variance`, `period`.

`BudgetScenario` : simulation `What-if` — clone d'un budget avec deltas, statut draft/validated.

`BudgetSpend` : dépense engagée/payée, `budget_line`, `amount`, `vendor`, `invoice_ref`, `validated_by`, `imported_from_integration` (option).

## 14. App `risks`

`Risk` :
- `ref` (`RSK-2026-0007`), `title`, `description_md`
- `category` (operational/financial/cyber/legal/strategic/hr)
- `impact` (1-5), `probability` (1-5), `severity` (computed = i × p)
- `status` (identified/assessed/mitigated/closed)
- `owner` (FK User), `direction` (FK)

`RiskAssessment` : revue datée (assessor, impact, probability, comments).

`RiskMitigation` : plan d'atténuation → souvent lié à `ActionPlan`.

`Incident` : incident réalisé — `risk` (FK option), `severity`, `detected_at`, `resolved_at`, `lessons_learned_md`.

`Compliance` : exigence réglementaire (RGPD, ISO, sectorielle), `status`, `next_audit`, `responsible`.

## 15. App `reports`

`ReportTemplate` : template avec format de sortie (docx/xlsx/pdf/pptx) + DSL (Jinja-like).

`ReportRun` : exécution. `template`, `parameters_json`, `requested_by`, `status`, `output_file` (FK `documents.Document`), `started_at`, `completed_at`, `error`.

`ScheduledReport` : récurrence (cron) avec destinataires.

## 16. App `analytics`

Vues matérialisées et tables d'agrégat pour le reporting cross-app :

`KPICubeDaily` : (organization, kpi, direction, date) → value. Refresh nightly + on-demand.

`DecisionCubeMonthly` : (organization, direction, status, month) → count + total_budget.

`MeetingCubeWeekly` : indicateurs CODIR (nb réunions, durée moyenne, taux de présence).

`Forecast` : prédiction d'un KPI — `kpi`, `horizon_periods`, `algorithm` (prophet/neural/manual), `forecast_json`, `mape`.

## 17. App `ai_engine`

`AIConversation` : conversation copilote utilisateur. `user`, `context_scope` (org/meeting/decision/dashboard), `started_at`.

`AIMessage` : message — `role` (user/assistant/system/tool), `content_md`, `tokens`, `citations_json`, `tool_calls_json`.

`AIInferenceLog` : log de chaque inférence (immutable) — `capability`, `provider`, `model`, `tokens_in`, `tokens_out`, `latency_ms`, `cost_usd`, `cached`, `request_hash`, `success`, `error`, `actor`.

`AIDocumentEmbedding` : embeddings RAG — `document`, `chunk_index`, `content_text`, `embedding` (`pgvector(3072)`), `lang`. Index HNSW.

`AIGlossary` : terminologie métier tenant (sigles, noms internes) injectée dans les prompts pour cohérence.

## 18. App `realtime`

`PresenceEntry` : éphémère (Redis) — typiquement non persisté en DB, mais on garde une table optionnelle pour analytics.

`Notification`, voir app dédiée.

`CollaborationDoc` : binaire Yjs pour les notes collaboratives (`updates` blob, `state_vector`). Snapshots quotidiens.

## 19. App `notifications`

`NotificationTemplate` : par event_type et par locale, avec variantes par canal.

`Notification` : instance — `recipient`, `event_type`, `subject`, `body_md`, `payload_json`, `priority`, `seen_at`, `acted_at`.

`NotificationChannel` : config canal — type (email/sms/whatsapp/push/inapp/teams), credentials, défauts.

`NotificationDelivery` : delivery par canal — `channel`, `notification`, `provider_message_id`, `status` (queued/sent/delivered/failed/bounced), `attempts`.

`NotificationPreference` : préférences utilisateur — par event_type & canal.

## 20. App `documents`

`Document` : entité racine — `name`, `mime`, `size`, `category`, FK `folder`, `current_version` (FK), `is_confidential`, `retention_until`, `signed_at`, `signature_provider`.

`DocumentVersion` : `number`, `file` (S3 path), `uploader`, `comment`, `checksum_sha256`.

`Folder` : arborescence — `parent` (FK self), `name`, `path`.

`DocumentAnnotation` : annotations sur un PDF — `page`, `coords`, `comment`, `author`, `version_target`.

`DocumentPermission` : ACL granulaire (override RBAC) — `user/role`, `document`, `permission` (view/edit/sign/share).

`SignatureRequest` : workflow signature électronique — `document`, `signers` (ordered), `provider` (Yousign/DocuSign/internal), `status`.

## 21. App `search`

`SearchIndex` : meta-modèle décrivant ce qui est indexé (App + mapping OpenSearch).

`SearchSuggestion` : queries fréquentes, complétion typeahead.

`SavedSearch` : recherche enregistrée par utilisateur (avec alertes possibles).

## 22. App `integrations`

`Integration` : configuration tenant — `provider` (sap/odoo/sage/m365/google/teams/zoom/whatsapp/sharepoint/powerbi/custom), `auth_type`, `is_active`, `last_sync_at`.

`IntegrationCredential` : credentials chiffrés (OAuth tokens, API keys).

`IntegrationSyncRun` : exécution d'une synchro — `started_at`, `completed_at`, `records_in`, `records_out`, `errors_json`.

`Webhook` : sortants — `event`, `target_url`, `secret`, `headers`, `is_active`.

`WebhookDelivery` : audit livraison webhook — `status`, `attempts`, `response_code`.

## 23. App `audit_logs`

`AuditEntry` (immutable, chained, signed) :
- `organization`, `actor` (User option, null pour system)
- `action` (created/updated/deleted/custom)
- `target_type` (CT), `target_id` (UUID/str), `target_repr`
- `before_json`, `after_json`, `diff_json`
- `ip`, `user_agent`, `request_id`, `device_fingerprint`
- `timestamp`
- `previous_hash`, `signature` (HMAC-SHA-256)
- `extra_json` (libre pour custom events)

Index `(organization, timestamp DESC)`, `(target_type, target_id, timestamp DESC)`.

## 24. App `mobile_api`

Pas de modèle métier — apps consomme tous les modèles existants via des **endpoints DRF optimisés mobile** (payloads compacts, delta sync). Une table `MobileDevice` (FK user, push token FCM/APNs, model, OS, app version, last seen).

## 25. App `administration`

`TenantSettings` : flags par fonctionnalité (modules activés, options branding, politique de mots de passe).

`AIConfiguration` : voir doc 06.

`FeatureFlag` : flags applicatifs (rollout progressif des features).

`Plan` : plans commerciaux référentiel.

`Invoice` : facturation tenant (à minima v1, intégration Stripe/Octobat v2).

## 26. Indexes critiques et performance

| Table | Indexes critiques |
|---|---|
| `decisions_decision` | `(organization, status, deadline)`, `(organization, responsible)`, `(organization, direction, status)` |
| `meetings_meeting` | `(organization, scheduled_start)`, `(codir_instance, scheduled_start)` |
| `kpis_kpisnapshot` | `(kpi, period_start)` BRIN sur period_start; partitionnement mensuel |
| `audit_logs_auditentry` | `(organization, timestamp)`, `(target_type, target_id)`; partitionnement mensuel |
| `ai_engine_aidocumentembedding` | HNSW sur `embedding`, `(organization, document)` |
| `notifications_notification` | `(recipient, seen_at, priority)` partial sur `seen_at IS NULL` |
| `action_plans_actiontask` | `(action_plan, status)`, `(assignee, due_date)` |

## 27. Volume estimé

| Table | Volume 12 mois (100 tenants) | Volume 36 mois (500 tenants) |
|---|---|---|
| Audit entries | 50 M | 750 M (partitionné) |
| KPI snapshots | 30 M | 400 M (partitionné) |
| AI inference logs | 10 M | 150 M |
| Document embeddings | 5 M | 60 M |
| Decisions | 200 k | 2 M |
| Meetings | 50 k | 600 k |
| Notifications | 100 M | 1 Mds (partitionné + TTL) |

Stratégie : partitionnement déclaratif PG 16 (range monthly) sur audit, KPI snapshots, AI logs, notifications. Archivage à froid (Parquet sur S3 + ClickHouse en option pour analytics OLAP lourd).

---

*Code Django exécutable : voir `backend/apps/*/models.py`.
Suite doc : [11 — API REST](11_api_rest.md)*
