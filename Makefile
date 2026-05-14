# CODIR — Makefile
# Commandes courantes pour dev et prod. `make help` pour la liste.

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend/web

help: ## Liste les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Dev environment ────────────────────────────────────

up: ## Lance la stack complète (dev)
	cd $(BACKEND_DIR) && docker compose up -d

down: ## Arrête la stack
	cd $(BACKEND_DIR) && docker compose down

logs: ## Logs en live
	cd $(BACKEND_DIR) && docker compose logs -f --tail=200

restart-api: ## Redémarre l'API Django (sans toucher DB)
	cd $(BACKEND_DIR) && docker compose restart api asgi worker-default worker-notifications beat

# ─── Backend ────────────────────────────────────────────

migrate: ## Applique les migrations
	cd $(BACKEND_DIR) && python manage.py migrate

makemigrations: ## Crée les migrations manquantes
	cd $(BACKEND_DIR) && python manage.py makemigrations

seed: ## Seed la donnée de démo (--reset purge)
	cd $(BACKEND_DIR) && python manage.py seed_beta --reset

shell: ## Shell Django
	cd $(BACKEND_DIR) && python manage.py shell

test: ## Lance les tests pytest
	cd $(BACKEND_DIR) && pytest -q

createsuperuser: ## Crée un super-admin
	cd $(BACKEND_DIR) && python manage.py createsuperuser

dedupe: ## Nettoie les doublons décisions/tâches
	cd $(BACKEND_DIR) && python manage.py dedupe_decisions

# ─── Celery (en local sans Docker) ──────────────────────

worker: ## Lance un worker Celery local
	cd $(BACKEND_DIR) && celery -A config worker -l info -Q default,notifications

beat: ## Lance Celery beat local
	cd $(BACKEND_DIR) && celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler

# ─── Frontend ──────────────────────────────────────────

front-install: ## npm install du frontend
	cd $(FRONTEND_DIR) && npm install

front-dev: ## Lance Vite dev server
	cd $(FRONTEND_DIR) && npm run dev

front-build: ## Build de prod
	cd $(FRONTEND_DIR) && npm run build

front-typecheck: ## Vérification TS
	cd $(FRONTEND_DIR) && npm run typecheck

# ─── Production ────────────────────────────────────────

prod-build: ## Build des images prod
	cd $(BACKEND_DIR) && docker compose -f docker-compose.prod.yml --env-file .env.prod build

prod-up: ## Démarre la stack prod
	cd $(BACKEND_DIR) && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

prod-down: ## Arrête la stack prod
	cd $(BACKEND_DIR) && docker compose -f docker-compose.prod.yml --env-file .env.prod down

prod-migrate: ## Migrations en prod
	cd $(BACKEND_DIR) && docker compose -f docker-compose.prod.yml --env-file .env.prod \
		run --rm api /app/scripts/docker-entrypoint.sh migrate

# ─── Maintenance / cleanup ─────────────────────────────

clean-pyc: ## Supprime les .pyc
	find $(BACKEND_DIR) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND_DIR) -name "*.pyc" -delete

clean-node: ## Supprime node_modules
	rm -rf $(FRONTEND_DIR)/node_modules

# ─── Génération de clés JWT RSA (prod) ─────────────────

jwt-keys: ## Génère une paire de clés JWT RSA 2048 dans deploy/
	mkdir -p $(BACKEND_DIR)/deploy/keys
	openssl genrsa -out $(BACKEND_DIR)/deploy/keys/jwt-private.pem 2048
	openssl rsa -in $(BACKEND_DIR)/deploy/keys/jwt-private.pem \
		-pubout -out $(BACKEND_DIR)/deploy/keys/jwt-public.pem
	@echo "Clés générées dans backend/deploy/keys/ — à charger dans .env.prod via env vars."

.PHONY: help up down logs restart-api migrate makemigrations seed shell test \
        createsuperuser dedupe worker beat front-install front-dev front-build \
        front-typecheck prod-build prod-up prod-down prod-migrate clean-pyc \
        clean-node jwt-keys
