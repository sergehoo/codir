# 20 — DevOps & CI/CD

## 1. Stratégie globale

**Trunk-based development.** Une branche principale `main` toujours déployable. Feature branches courtes (< 3 jours), squash merge après review. Releases via tags `v1.x.y` semver.

**Environnements.**
- `dev` — local, docker-compose.
- `staging` — K8s identique prod, données factices + 1 tenant pilote.
- `prod-eu` — production EU (frankfurt + paris).
- `prod-us` — v2 (à activer).
- `prod-sovereign-<client>` — déploiement dédié on-prem (édition Sovereign).

**Stratégie de release.** Continuous deployment vers staging à chaque merge sur `main`. Promotion vers prod manuelle (un click GitHub Actions) après validation QA. Rollback en < 5 min via Argo CD `app rollback` ou `kubectl rollout undo`.

## 2. CI/CD avec GitHub Actions

### 2.1. Workflow principal (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ruff mypy black
      - run: ruff check backend/
      - run: black --check backend/
      - run: mypy backend/

  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
        options: >-
          --health-cmd="pg_isready" --health-interval=5s
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - run: cd backend && pytest --cov=apps --cov=core --cov-report=xml -n auto
      - uses: codecov/codecov-action@v4

  security-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install bandit safety
      - run: bandit -r backend/
      - run: safety check -r backend/requirements.txt
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: codir-backend:${{ github.sha }}

  build-backend-image:
    needs: [test-backend, lint-backend, security-backend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: backend/
          push: true
          tags: |
            ghcr.io/codir/backend:${{ github.sha }}
            ghcr.io/codir/backend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Sign image with Cosign
        run: cosign sign --yes ghcr.io/codir/backend:${{ github.sha }}

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend/web && pnpm install --frozen-lockfile
      - run: cd frontend/web && pnpm lint
      - run: cd frontend/web && pnpm typecheck
      - run: cd frontend/web && pnpm test:ci
      - run: cd frontend/web && pnpm build

  e2e:
    needs: [build-backend-image]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.e2e.yml up -d
      - run: cd frontend/web && pnpm install && pnpm playwright install
      - run: cd frontend/web && pnpm playwright test
      - if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/web/playwright-report/

  deploy-staging:
    needs: [e2e]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Setup kubectl
        uses: azure/setup-kubectl@v3
      - name: Configure kubeconfig
        run: echo "${{ secrets.STAGING_KUBECONFIG }}" > kubeconfig
      - name: Argo CD app sync
        run: |
          argocd app set codir-backend --image ghcr.io/codir/backend:${{ github.sha }}
          argocd app sync codir-backend --prune
          argocd app wait codir-backend --timeout 600
```

### 2.2. Workflow de release prod (manuel)

```yaml
name: Release production

on:
  workflow_dispatch:
    inputs:
      sha:
        description: SHA validé en staging
        required: true
      region:
        type: choice
        options: [prod-eu]

jobs:
  promote:
    runs-on: ubuntu-latest
    environment: ${{ inputs.region }}
    steps:
      - uses: actions/checkout@v4
      - name: Verify Cosign signature
        run: cosign verify ghcr.io/codir/backend:${{ inputs.sha }} --certificate-identity-regexp '.*'
      - name: Promote via Argo CD
        run: |
          argocd app set codir-backend-${{ inputs.region }} --image ghcr.io/codir/backend:${{ inputs.sha }}
          argocd app sync codir-backend-${{ inputs.region }} --strategy=blue-green
```

## 3. Conteneurisation

### 3.1. Dockerfile backend (multi-stage)

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini && rm -rf /var/lib/apt/lists/*

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libsndfile1
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=app:app . .
USER app
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gthread", "--threads", "8"]
```

Variantes : `Dockerfile.asgi` (Daphne pour WS), `Dockerfile.worker` (Celery), `Dockerfile.beat`.

### 3.2. docker-compose (dev local)

Voir `backend/docker-compose.yml` (fourni dans le scaffolding).

### 3.3. Kubernetes & Helm

Un chart Helm unique `codir/` paramétrable par valeurs (replicas, ressources, tenant, edition). Sous-charts pour : `api`, `asgi`, `worker-default`, `worker-ai`, `worker-reports`, `worker-integrations`, `beat`. Dépendances : `postgresql` (bitnami), `redis`, `opensearch`, `minio`.

Manifests gérés par **Argo CD** (GitOps). Repo séparé `codir-deploy/` qui décrit l'état de chaque environnement.

## 4. Infrastructure as Code

**Terraform** pour le provisioning des clusters K8s, des bases managées (Postgres, Redis si managés), du DNS, des certificats. Stack par environnement, modules réutilisables.

```
infra/
├── modules/
│   ├── kubernetes-cluster/
│   ├── postgres-rds/
│   ├── redis-elasticache/
│   ├── opensearch/
│   └── object-storage/
├── envs/
│   ├── staging/
│   ├── prod-eu/
│   └── prod-sovereign-template/
└── shared/
    ├── dns/
    ├── iam/
    └── vault/
```

## 5. Secrets

**HashiCorp Vault** (ou cloud-native KMS). Aucun secret en clair :
- DB credentials gérés par Vault dynamic secrets (rotation 1h).
- API keys (OpenAI, Stripe, Yousign) en static secret, rotation manuelle 90 j.
- Clés JWT (RS256) en Vault Transit, signature côté Django via Vault si on choisit l'option (sinon, montage volume tmpfs).
- Backups encryption keys séparés (HSM YubiHSM ou cloud HSM).

## 6. Bases de données — gestion

**Migrations Django** : `python manage.py migrate` exécuté en init container de chaque déploiement.
**Backup** : `pg_dump` quotidien + WAL archivé via `wal-g` vers MinIO/S3 cross-region. Rétention : 30 j chauds, 12 mois froids. PITR à la minute.
**Performance** : analyse régulière via `pg_stat_statements`, `pgBadger` weekly report, ajout d'index sur recommendation explicite uniquement (jamais aveuglément).
**Scaling lecture** : read replicas pour les dashboards & reports lourds (`router DB` Django).

## 7. Branches et review

- **Branches** : trunk-based, branches < 3 jours.
- **PR template** : description, screenshots, checklist (tests, doc, perf, sécurité), risques de rollback.
- **Reviews** : 1 minimum, 2 pour zones sensibles, codeowners auto-assignés.
- **Bots** : Dependabot (sécurité critique automatique merge), Renovate (mise à jour libs minor).

## 8. Versioning et releases

- **Semver** strict.
- **CHANGELOG.md** maintenu via conventional commits (`fix:`, `feat:`, `BREAKING CHANGE:`).
- **Release notes** publiées sur portail client.

## 9. Feature flags

**Flagsmith** (ou Unleash en self-host). Permet : rollouts progressifs, A/B testing IA, désactivation rapide d'une feature buggée sans rollback.

## 10. Performance et SRE

**SLO 99,9 % availability sur l'API** mesuré sur des sondes synthétiques + traffic réel. Erreur budget 43 min/mois. Quand le budget tombe < 30 %, freeze des features non critiques.

**Latence p99 < 400 ms** sur les endpoints REST. p99 WS < 200 ms application.

**Tests de charge** mensuels (Locust scénario réaliste : 1000 utilisateurs simultanés répartis 70 % lecture / 25 % écriture / 5 % live).

## 11. Sécurité opérationnelle

- **Image signing** Cosign systématique.
- **Admission control** K8s via Kyverno (refuser images non signées, refuser pods sans resources limits).
- **Network policies** strictes (default deny, allow explicit).
- **mTLS** entre services (cert-manager + Linkerd ou Istio en v2).
- **Pod Security Standards** : niveau `restricted`.

## 12. Documentation runbooks

Tout incident type a un runbook dans `docs/runbooks/` :
- Postgres failover
- Redis split-brain
- OpenSearch rebalance
- Celery queue saturée
- Token JWT compromis (rotation d'urgence)
- Tenant compromis (verrouillage)
- IA fournisseur down (basculement Ollama)
- Backup restore

## 13. Onboarding développeur

Nouveau dev productif en < 4 h :
1. Clone du repo + `make setup` (installe pre-commit, vault token, env file).
2. `make up` (docker-compose lance toute la stack locale).
3. `make seed` (charge données de démo + 2 tenants test).
4. `make test`, `make e2e` (vérification).
5. Lecture obligatoire des docs 01, 02, 09, 13.
6. Pair programming 1/2 journée sur la première PR.

---

*Suite : [21 — Monitoring](21_monitoring.md)*
