# 21 — Monitoring & Observabilité

## 1. Les trois piliers de l'observabilité

CODIR implémente les trois piliers — **métriques, logs, traces** — orchestrés via OpenTelemetry pour une vue unifiée. Sentry complète sur les erreurs applicatives.

| Pilier | Outil principal | Stockage | Visualisation |
|---|---|---|---|
| Métriques | Prometheus | Mimir (longue rétention) | Grafana |
| Logs | Loki (+ Promtail) | S3 backend | Grafana |
| Traces | Tempo (OpenTelemetry) | S3 backend | Grafana |
| Erreurs | Sentry | Sentry SaaS / self-host | Sentry UI |
| Synthétiques | Grafana Synthetic Monitoring | — | Grafana |

## 2. Métriques applicatives

### 2.1. Métriques Django exposées

`/metrics` endpoint protégé (network policy K8s, scope interne). Métriques custom :

```
codir_http_requests_total{tenant, route, method, status}
codir_http_request_duration_seconds_bucket{tenant, route, method}
codir_db_query_duration_seconds_bucket{tenant, query_type}
codir_celery_task_duration_seconds_bucket{tenant, task_name, queue}
codir_celery_task_total{tenant, task_name, queue, status}
codir_celery_queue_length{queue}
codir_ws_connections_total{scope}
codir_ws_active_connections{scope}
codir_ws_messages_sent_total{scope, type}
codir_ai_inference_total{tenant, capability, provider, status}
codir_ai_inference_duration_seconds_bucket{capability, provider}
codir_ai_tokens_total{tenant, capability, provider, direction}
codir_ai_cost_usd_total{tenant, capability, provider}
codir_decision_lifecycle_seconds_bucket{tenant, transition}
codir_meeting_duration_seconds_bucket{tenant}
codir_kpi_breach_total{tenant, kpi_code, level}
codir_audit_entries_total{tenant, action}
codir_storage_bytes_used{tenant, type}
codir_active_users{tenant, window=5m|1h|24h}
```

### 2.2. Métriques infra

Node exporter (CPU/RAM/disk/IO/net), kube-state-metrics (pods, deployments), Postgres exporter, Redis exporter, OpenSearch exporter, MinIO Prometheus endpoint, Traefik metrics endpoint.

### 2.3. Métriques produit (Northstar)

Métriques business poussées par jobs Celery nightly :

```
codir_business_active_tenants
codir_business_active_users_weekly
codir_business_meetings_held_total
codir_business_decisions_created_total
codir_business_decisions_completion_rate
codir_business_pv_generated_total
codir_business_pv_review_duration_seconds
```

## 3. Logs structurés

Tous les logs sont JSON, comportent : `timestamp`, `level`, `logger`, `message`, `tenant_id`, `user_id`, `request_id`, `trace_id`, `span_id`, et tout autre contexte pertinent. Envoyés à Loki via Promtail.

Logging Python configuration :

```python
LOGGING = {
    "version": 1,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"level": "WARNING"},
        "apps.audit_logs": {"level": "INFO"},
    },
}
```

Niveaux : `DEBUG` (dev only), `INFO` (mutations métier, démarrages services), `WARNING` (anomalies non-bloquantes), `ERROR` (échecs métier ou techniques), `CRITICAL` (alertes immédiates).

## 4. Traces distribuées (OpenTelemetry)

Auto-instrumentation Django, DRF, Celery, psycopg, Redis, requests. Échantillonnage 100 % en staging, 10 % en prod (au-delà : adaptive sampling sur erreurs).

Custom spans pour les pipelines longs (génération PV) — chaque étape devient un span enfant.

## 5. Sentry (errors)

Tous les crashs serveur, toutes les unhandled exceptions front. Releases trackées (lien commit → exception). Performance tracing (10 % d'échantillonnage). Source maps front uploadées au build. PII scrubbed (numéros de carte, mots de passe).

## 6. Dashboards Grafana

Set de dashboards préconfigurés et provisionnés via code (Grafana provisioning) :

- **Overview** — état global, RED metrics (Rate, Errors, Duration).
- **API performance** — par endpoint et par tenant top 10.
- **WebSocket** — connexions, latence, taux de disconnect.
- **Celery** — queue length, task duration, error rate.
- **IA** — inférences, tokens, coûts, latence par capability.
- **Business** — Northstar metrics.
- **Postgres** — connections, slow queries, lock waits, bloat.
- **Storage** — bytes by tenant, growth rate.
- **Tenant** — drill par tenant pour le support (charge, erreurs, latence).
- **SRE** — SLO + error budget burn rate.

## 7. Alerting

**Prometheus Alertmanager** route vers PagerDuty (production), Slack `#alerts-{severity}` (dev), et Email (résumé quotidien).

Alertes critiques (P1, page on-call immédiat) :
- API 5xx rate > 1 % sur 5 min
- p99 latence > 2 s sur 10 min
- WS disconnect rate > 5 % sur 5 min
- DB connections > 80 % du pool
- Disk usage > 85 %
- Celery queue lag > 10 min
- 0 successful login en 5 min sur prod (sonde synthétique)
- Sentry erreur "exception inattendue" > 10/min

Alertes warning (P2, Slack + email seulement) :
- p99 latence > 800 ms
- WS connections > 80 % capacité worker
- Failed IA inference rate > 5 %
- Audit log signature mismatch (P0 en réalité — escalade immédiate)
- Tenant spend IA > 90 % budget

Alertes business (P3, daily digest) :
- WAU drop > 20 % vs semaine précédente
- Décisions complétées en retard > 30 %
- PV non finalisé > 7 jours

## 8. SLOs & error budgets

| SLO | Cible | Mesure | Budget mensuel |
|---|---|---|---|
| API availability | 99,9 % | sondes + traffic réel | 43 min |
| API p99 latency | < 400 ms | percentile sur 1 min | — |
| WS uptime | 99,9 % | sondes WS | 43 min |
| IA service success | 99 % | inférences ok / total | 7,2 h |
| Génération PV < 90 s | 95 % | mesure pipeline | 36 h |

Burn rate alerts (Google SRE style) :
- Burn 14,4× sur 1h → page immédiat (utilise > 2 % budget en 1h)
- Burn 6× sur 6h → page
- Burn 3× sur 24h → ticket non urgent

## 9. Sondes synthétiques

Scripts Playwright headless lancés depuis 3 régions (EU, US, AS) toutes les 5 min :
- Login + MFA
- Charger dashboard DG
- Créer une décision dummy
- Vérifier WebSocket connexion (mode meeting)

Synthetics échouées 2× consécutivement → alerte P1.

## 10. Audit observabilité

Le module `audit_logs` est lui-même observable :
- Métrique `codir_audit_entries_total` par action.
- Métrique `codir_audit_signature_mismatch_total` (devrait toujours être 0). Toute déviation est P0.
- Dashboard dédié pour les auditeurs internes (accès RBAC `audit:read_only`).

## 11. Cost monitoring

Métriques de coût remontées dans Grafana :

- Coût IA par tenant (extrait des `InferenceLog`).
- Coût infra estimé (CPU, RAM, storage) par tenant via `kube-state-metrics` + labels.
- Coût intégrations (appels SAP / Power BI facturés).

Permet la facturation à l'usage (v2) et la détection d'abus.

## 12. Tableaux de bord pour les rôles métier

L'observabilité ne sert pas qu'aux SRE. Trois dashboards Grafana sont exposés en lecture seule (auth via SSO) à des rôles non techniques :

- **Customer Success** — état des tenants pilotes : adoption, KPI usage, erreurs spécifiques.
- **Product Management** — funnel d'activation, taux d'adoption de chaque feature.
- **Sales Engineering** — uptime SLA pour rapports commerciaux clients.

## 13. Tests d'observabilité

Eh oui — l'observabilité elle-même doit être testée :
- Smoke tests sur les exporters Prometheus en CI.
- Validation des dashboards (yaml linting) en CI.
- Drills d'alerting (Gameday) trimestriels : on injecte des erreurs, on chronomètre la détection et la résolution.
- Postmortem des incidents : revue de "qu'aurions-nous aimé voir plus tôt ?", évolution du monitoring en sortie.

---

*Suite : [22 — Stratégie IA](22_strategie_ia.md)*
