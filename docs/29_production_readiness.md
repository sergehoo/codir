# Production Readiness — CODIR Executive Platform

Audit global avant mise en production. Les éléments ✅ sont prêts, ⚠️ à compléter, 🔴 bloquant.

---

## 1. Sécurité

| Statut | Item | Action |
|---|---|---|
| 🔴 | `.env` commité avec `weddingLIFE18` et autres mots de passe | Rotate Postgres password, ajouter `.gitignore`, purger l'historique git (`git filter-repo`). |
| 🔴 | Pas de `.gitignore` à la racine | **FAIT** — créé `.gitignore` racine. |
| ⚠️ | JWT en HS256 par défaut, RS256 forcé en prod uniquement | Générer la paire RSA via `make jwt-keys`, l'injecter dans `.env.prod`. |
| ⚠️ | CORS allow-credentials + wildcard en dev | `prod.py` lit `CORS_ALLOWED_ORIGINS` strictement — vérifier la valeur en prod. |
| ⚠️ | Throttles DRF globaux mais pas spécifiques à `/auth/login/` | Ajouter un scope custom dans `DEFAULT_THROTTLE_RATES` + `UserRateThrottle`. |
| ✅ | Multi-tenant strict (ContextVar) | Testé. |
| ✅ | Audit log signé | `apps/audit_logs/` actif. |
| ✅ | HSTS + secure cookies en prod | `prod.py`. |
| ⚠️ | Pas de Content Security Policy (CSP) | Ajouter django-csp ou middleware custom. |

## 2. Observabilité

| Statut | Item | Action |
|---|---|---|
| 🔴 | Aucun endpoint `/health/` | **FAIT** — `/health/` (liveness) + `/health/ready/` (DB + cache). |
| ⚠️ | `python-json-logger` référencé mais absent de `requirements.txt` | Ajouter à requirements ou supprimer le fallback. |
| ⚠️ | Sentry SDK installé mais `SENTRY_DSN` vide | À renseigner en prod. |
| ⚠️ | Pas d'OpenTelemetry / Prometheus | Ajout futur (cf. doc `06_observability.md`). |
| ⚠️ | `RequestIdMiddleware` existe mais pas de propagation aux logs | Compléter le formatter pour inclure `request_id`. |

## 3. DevOps / Docker

| Statut | Item | Action |
|---|---|---|
| 🔴 | docker-compose dev avec ancres YAML mal placées | **FAIT** — refonte complète, ancres en haut, healthcheck API, init MinIO. |
| 🔴 | Pas de `docker-compose.prod.yml` | **FAIT** — fichier dédié avec env strict, gunicorn, nginx, frontend. |
| 🔴 | Pas de Dockerfile frontend | **FAIT** — `frontend/web/Dockerfile` (multi-stage Vite + Nginx). |
| 🔴 | Pas de reverse-proxy / TLS | **FAIT** — `backend/deploy/nginx.conf` (TLS, WS, rate-limit auth). |
| 🔴 | Pas de `docker-entrypoint.sh` (race condition au démarrage) | **FAIT** — `backend/scripts/docker-entrypoint.sh` (wait-for-db, migrate, collectstatic, gunicorn). |
| 🔴 | Pas de Makefile | **FAIT** — `Makefile` racine (up/down/migrate/test/prod-build…). |
| ⚠️ | Pas de CI/CD GitHub Actions | À créer dans `.github/workflows/`. |
| ⚠️ | Pas de scan vulnérabilités image | Ajouter `trivy` ou `docker scout` au pipeline. |

## 4. Migrations & data

| Statut | Item | Action |
|---|---|---|
| ⚠️ | `notifications.0002` doit être appliqué (fields nouveaux) | `python manage.py migrate notifications`. |
| ⚠️ | `meetings.0002_smart_notes` à appliquer | `python manage.py migrate meetings`. |
| ⚠️ | Pas de `backups` planifiés Postgres | Configurer `pg_dump` cron + S3 retention 30j. |
| ⚠️ | Doublons décisions/actions historiques | `python manage.py dedupe_decisions`. |

## 5. Email & Notifications

| Statut | Item | Action |
|---|---|---|
| ✅ | SMTP env-driven | Hostinger ready. |
| ✅ | Templates HTML/text Atelier-branded | 7 templates. |
| ✅ | Celery beat rappels 09h/16h | `Africa/Abidjan`. |
| ⚠️ | Pas d'endpoint `test-email` documenté | **FAIT** — `POST /api/v1/notifications/test-email/`. |
| ⚠️ | Quiet hours UI ok mais worker ne filtre pas | Compléter `send_user_task_reminder` pour respecter `quiet_hours_start/end`. |

## 6. Tests

| Statut | Item | Action |
|---|---|---|
| ⚠️ | Couverture ~17% (5 fichiers de tests sur 12 apps) | Cible bêta : couvrir auth, decisions, action_plans, notifications. |
| ⚠️ | Pas de tests d'intégration API | Ajouter pytest-django + APIClient sur scénarios end-to-end. |
| ⚠️ | Pas de tests frontend | Vitest installé, à enrichir (ex: `SmartMeetingEditor` parser). |
| ⚠️ | Pas de tests E2E (Playwright/Cypress) | Phase post-bêta. |

## 7. Frontend

| Statut | Item | Action |
|---|---|---|
| 🔴 | `.env.example` frontend manquant | **FAIT** — `frontend/web/.env.example`. |
| ⚠️ | Tiptap dans `package.json` mais `npm install` à relancer | `npm install` dans `frontend/web/`. |
| ⚠️ | Pas de Sentry SDK frontend | Ajouter `@sentry/react` si `VITE_SENTRY_DSN` configuré. |
| ⚠️ | Lucide-react warnings TypeScript (mineurs) | Mettre à jour à `lucide-react@^0.460.0`. |
| ✅ | Build Vite + Tailwind + Atelier | OK. |
| ✅ | Routes guard JWT | OK. |

## 8. Architecture / périmètre

| Statut | Item | Action |
|---|---|---|
| ✅ | 12 apps actives en bêta | meetings, agendas, decisions, action_plans, notifications, accounts, organizations, governance, documents, audit_logs, dashboards, common. |
| ⚠️ | 11 apps désactivées avec migrations | `administration`, `ai_engine`, `analytics`, `budgets`, `codir`, `integrations`, `kpis`, `mobile_api`, `realtime`, `reports`, `risks`, `search`, `workflows`. Décider : supprimer du repo ou garder en suspens. |

---

## Quick start — déploiement minimal

```bash
# 1) Générer les clés JWT RSA
make jwt-keys

# 2) Renseigner .env.prod (à partir du .env.prod.example)
cp backend/.env.prod.example backend/.env.prod
# … éditer …

# 3) Build des images
make prod-build

# 4) Lancer la stack
make prod-up

# 5) Premier seed (optionnel — sinon créer un superuser)
make prod-migrate
docker compose -f backend/docker-compose.prod.yml --env-file backend/.env.prod \
  run --rm api python manage.py createsuperuser

# 6) Vérifier /health/ready/ retourne 200
curl https://api.codir.example.com/health/ready/
```

---

## Liste des bloquants restants (rapide)

1. **Rotate les secrets** dans `backend/.env` (Postgres, S3…) — ils sont visibles dans l'historique git.
2. **Appliquer les 2 migrations** : `meetings.0002`, `notifications.0002` (+`0003`).
3. **`make front-install`** — relancer pour Tiptap.
4. **Setup Sentry** côté backend + frontend (10 min).
5. **Configurer un Postgres managé** en prod (RDS / CloudSQL / OVH Managed PostgreSQL).
6. **Backups automatiques** Postgres + S3 lifecycle policy 30 jours.
7. **CI minimale** : un workflow `.github/workflows/ci.yml` qui lance `pytest` + `npm run typecheck` + build images.
8. **Certificats TLS** : Let's Encrypt via certbot ou Caddy. Volume `deploy/certs/`.

Une fois ces 8 points clos, la bêta peut accueillir des utilisateurs externes.
