# CODIR — Executive Operating System

> Plateforme SaaS de Gouvernance et de Pilotage du Comité de Direction
> *Cockpit Exécutif Intelligent — AI Governance Platform*

---

## 1. Pitch en une ligne

**CODIR** est l'OS exécutif d'une grande organisation : il orchestre la préparation des comités de direction, la prise de décision, l'exécution des résolutions, le pilotage des KPI stratégiques et la gouvernance — le tout piloté par une IA native qui rédige les comptes rendus, détecte les risques, et oriente l'action.

## 2. Public cible

Groupes industriels • Ministères • Banques et assurances • Hôpitaux et CHU • Collectivités et Smart Cities • Holdings multi-filiales • DG, Présidents, DAF, DRH, DSI, PMO, Audit, Compliance.

## 3. Stack — vue d'ensemble

| Couche | Technologies |
|---|---|
| **Backend** | Django 6, DRF, PostgreSQL 16, Redis 7, Celery, Django Channels, JWT, RBAC, OpenSearch |
| **Frontend Web** | React 18, TypeScript, TailwindCSS, Shadcn/UI, Tanstack Query, Zustand, ECharts, Framer Motion |
| **Mobile** | Flutter 3.x, Hive (offline), FCM, biométrie native |
| **IA** | OpenAI + Ollama, LangChain, RAG (pgvector), Whisper (STT), NLP custom |
| **Infra** | Docker Compose / K8s, Traefik, MinIO/S3, Prometheus, Grafana, Loki, Sentry, GitHub Actions |

## 4. Modules fonctionnels (23 apps Django)

```
accounts · organizations · governance · codir · meetings · agendas
decisions · action_plans · workflows · dashboards · kpis · budgets
risks · reports · analytics · ai_engine · realtime · notifications
documents · search · integrations · audit_logs · mobile_api · administration
```

## 5. Organisation du repo

```
codir/
├── README.md                  ← vous êtes ici
├── docs/                      ← Architecture, modélisation, roadmap (25 documents)
│   ├── 01_vision_produit.md
│   ├── 02_architecture_globale.md
│   ├── 03_architecture_backend.md
│   ├── 04_architecture_frontend.md
│   ├── 05_architecture_mobile.md
│   ├── 06_architecture_ia.md
│   ├── 07_architecture_temps_reel.md
│   ├── 08_architecture_securite.md
│   ├── 09_architecture_multi_tenant.md
│   ├── 10_modeles_donnees.md
│   ├── 11_api_rest.md
│   ├── 12_websocket.md
│   ├── 13_rbac.md
│   ├── 14_workflows_metiers.md
│   ├── 15_dashboards.md
│   ├── 16_ux_ui.md
│   ├── 17_roadmap_produit.md
│   ├── 18_roadmap_technique.md
│   ├── 19_sprint_planning.md
│   ├── 20_devops_cicd.md
│   ├── 21_monitoring.md
│   ├── 22_strategie_ia.md
│   ├── 23_integrations.md
│   ├── 24_diagrammes.md
│   └── 25_features_premium.md
├── backend/                   ← Squelette Django production-ready
│   ├── config/                ← settings (base/dev/prod), urls, asgi
│   ├── apps/                  ← 23 apps avec models.py exécutables
│   ├── requirements.txt
│   ├── docker-compose.yml
│   └── Dockerfile
├── frontend/
│   └── mockups/               ← Maquettes HTML interactives
│       ├── index.html
│       ├── dashboard_dg.html
│       ├── dashboard_daf.html
│       ├── meeting_live.html
│       ├── ai_assistant.html
│       └── mobile_executive.html
└── codir/                     ← Projet Django initial (legacy, à migrer vers backend/)
```

## 6. Démarrage rapide (cible)

```bash
# Backend
cd backend
docker compose up -d           # postgres, redis, opensearch, minio, traefik
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Frontend (à venir)
cd frontend/web
pnpm install && pnpm dev

# Mobile (à venir)
cd mobile
flutter run
```

## 7. Principes directeurs

1. **API-first** — tout passe par DRF, le web et le mobile sont des clients
2. **Event-driven** — Celery + Channels pour découpler asynchrone et temps réel
3. **Multi-tenant** par défaut — isolation logique stricte par `Organization`
4. **Audit-by-design** — chaque mutation laisse une trace inaltérable
5. **AI-native** — l'IA n'est pas un bolt-on, elle est dans les workflows
6. **Zero-trust** — chiffrement, MFA, RBAC, journalisation, rotation des secrets

## 8. Sommaire des livrables produits

| # | Livrable | Localisation |
|---|---|---|
| 1 | Vision produit | `docs/01_vision_produit.md` |
| 2 | Architecture globale | `docs/02_architecture_globale.md` |
| 3 | Architecture backend | `docs/03_architecture_backend.md` |
| 4 | Architecture frontend | `docs/04_architecture_frontend.md` |
| 5 | Architecture mobile | `docs/05_architecture_mobile.md` |
| 6 | Architecture IA | `docs/06_architecture_ia.md` |
| 7 | Architecture temps réel | `docs/07_architecture_temps_reel.md` |
| 8 | Architecture sécurité | `docs/08_architecture_securite.md` |
| 9 | Architecture multi-tenant | `docs/09_architecture_multi_tenant.md` |
| 10 | Modèles de données | `docs/10_modeles_donnees.md` |
| 11 | API REST | `docs/11_api_rest.md` |
| 12 | WebSockets | `docs/12_websocket.md` |
| 13 | RBAC | `docs/13_rbac.md` |
| 14 | Workflows métiers | `docs/14_workflows_metiers.md` |
| 15 | Dashboards | `docs/15_dashboards.md` |
| 16 | UX/UI | `docs/16_ux_ui.md` |
| 17 | Roadmap produit | `docs/17_roadmap_produit.md` |
| 18 | Roadmap technique | `docs/18_roadmap_technique.md` |
| 19 | Sprint planning | `docs/19_sprint_planning.md` |
| 20 | DevOps & CI/CD | `docs/20_devops_cicd.md` |
| 21 | Monitoring | `docs/21_monitoring.md` |
| 22 | Stratégie IA | `docs/22_strategie_ia.md` |
| 23 | Intégrations | `docs/23_integrations.md` |
| 24 | Diagrammes UML / séquence / archi | `docs/24_diagrammes.md` |
| 25 | Fonctionnalités premium | `docs/25_features_premium.md` |
| 26 | Modèles Django exécutables | `backend/apps/*/models.py` |
| 27 | Mockups HTML | `frontend/mockups/*.html` |

---

*Document maintenu par l'équipe Architecture — version 1.0 — 13 mai 2026*
