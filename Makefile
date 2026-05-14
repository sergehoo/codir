# CODIR — Makefile racine
# Toutes les commandes Docker tournent depuis la racine (le compose y est).
# Backend Python et Celery local se lancent depuis backend/.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend/web

# Compose helper (DRY)
DC_DEV  := docker compose
DC_PROD := docker compose -f docker-compose.prod.yml --env-file .env.prod

help: ## Liste les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Dev environment (Docker, depuis racine) ────────────

up: ## Lance la stack dev complète (Traefik + DB + API + workers + frontend)
	$(DC_DEV) up -d

down: ## Arrête la stack dev
	$(DC_DEV) down

logs: ## Logs live (200 dernières lignes)
	$(DC_DEV) logs -f --tail=200

restart-api: ## Redémarre l'API Django (sans toucher DB)
	$(DC_DEV) restart api asgi worker-default worker-notifications beat

ps: ## État des conteneurs
	$(DC_DEV) ps

# ─── Backend (Python local) ─────────────────────────────

migrate: ## Applique les migrations (local)
	cd $(BACKEND_DIR) && python manage.py migrate

makemigrations: ## Crée les migrations manquantes (local)
	cd $(BACKEND_DIR) && python manage.py makemigrations

seed: ## Seed la donnée de démo (--reset purge)
	cd $(BACKEND_DIR) && python manage.py seed_beta --reset

shell: ## Shell Django (local)
	cd $(BACKEND_DIR) && python manage.py shell

test: ## pytest backend (local)
	cd $(BACKEND_DIR) && pytest -q

createsuperuser: ## Crée un super-admin (local)
	cd $(BACKEND_DIR) && python manage.py createsuperuser

dedupe: ## Nettoie les doublons décisions/tâches
	cd $(BACKEND_DIR) && python manage.py dedupe_decisions

# ─── Celery (local sans Docker) ──────────────────────────

worker: ## Lance un worker Celery local
	cd $(BACKEND_DIR) && celery -A config worker -l info -Q default,notifications

celery-beat: ## Lance Celery beat local
	cd $(BACKEND_DIR) && celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler

# ─── Frontend ──────────────────────────────────────────

front-install: ## npm install
	cd $(FRONTEND_DIR) && npm install

front-dev: ## Vite dev server (local, hors Docker)
	cd $(FRONTEND_DIR) && npm run dev

front-build: ## Build prod
	cd $(FRONTEND_DIR) && npm run build

front-typecheck: ## Vérification TS
	cd $(FRONTEND_DIR) && npm run typecheck

# ─── Production ────────────────────────────────────────

prod-build: ## Build des images prod (api + web)
	$(DC_PROD) build

prod-up: ## Démarre la stack prod (Traefik + Let's Encrypt)
	$(DC_PROD) up -d

prod-down: ## Arrête la stack prod
	$(DC_PROD) down

prod-restart: ## Redémarre uniquement l'app (rolling)
	$(DC_PROD) up -d --no-deps --build api asgi worker-default worker-notifications beat web

prod-migrate: ## Lance les migrations en prod
	$(DC_PROD) run --rm api /app/scripts/docker-entrypoint.sh migrate

prod-logs: ## Logs prod
	$(DC_PROD) logs -f --tail=200

prod-superuser: ## Crée un superuser en prod
	$(DC_PROD) run --rm api python manage.py createsuperuser

prod-shell: ## Shell Django en prod
	$(DC_PROD) run --rm api python manage.py shell

# ─── Backup Postgres ───────────────────────────────────

prod-backup: ## Dump Postgres prod → ./backups/<date>.sql.gz
	@mkdir -p backups
	$(DC_PROD) exec -T postgres pg_dump -U $${POSTGRES_USER:-codir} $${POSTGRES_DB:-codir} \
		| gzip > backups/codir-$$(date +%Y-%m-%d-%H%M).sql.gz
	@echo "Backup créé dans backups/"

# ─── Maintenance / cleanup ─────────────────────────────

clean-pyc: ## Supprime les .pyc
	find $(BACKEND_DIR) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND_DIR) -name "*.pyc" -delete

clean-node: ## Supprime node_modules
	rm -rf $(FRONTEND_DIR)/node_modules

# ─── Génération clés JWT RSA ───────────────────────────

jwt-keys: ## Génère une paire de clés RSA 2048 pour le JWT prod
	mkdir -p deploy/keys
	openssl genrsa -out deploy/keys/jwt-private.pem 2048
	openssl rsa -in deploy/keys/jwt-private.pem -pubout -out deploy/keys/jwt-public.pem
	@echo "✓ Clés générées dans deploy/keys/."
	@echo "  Copier le contenu (avec \\n littéraux) dans .env.prod :"
	@echo "    JWT_PRIVATE_KEY=\"\$$(cat deploy/keys/jwt-private.pem | sed ':a;N;\$$!ba;s/\\n/\\\\n/g')\""

# ─── Help & meta ───────────────────────────────────────

.PHONY: help up down logs ps restart-api migrate makemigrations seed shell test \
        createsuperuser dedupe worker celery-beat front-install front-dev front-build \
        front-typecheck prod-build prod-up prod-down prod-restart prod-migrate \
        prod-logs prod-superuser prod-shell prod-backup clean-pyc clean-node jwt-keys
