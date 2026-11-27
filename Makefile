.PHONY: help setup install install-dev run worker run-prod migrate frontend-install frontend-dev frontend-test frontend-typecheck frontend-build docker-build docker-up docker-down docker-logs test test-cov lint format type-check db-reset clean env health quick-start

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
ALEMBIC := $(VENV)/bin/alembic
UVICORN := $(VENV)/bin/uvicorn
GUNICORN := $(VENV)/bin/gunicorn

help:
	@echo "AcquireMock v2.0 - Available commands:"
	@echo "  make setup             - Create virtualenv, install backend & frontend deps"
	@echo "  make migrate           - Apply Alembic database migrations"
	@echo "  make run               - Start FastAPI dev server with reload"
	@echo "  make worker            - Start dedicated background webhook/expiry worker"
	@echo "  make run-prod          - Start production Gunicorn server"
	@echo "  make frontend-dev      - Start Vite dev server"
	@echo "  make frontend-test     - Run Vitest suite"
	@echo "  make frontend-build    - Build frontend assets into frontend/dist"
	@echo "  make test              - Run backend pytest and frontend Vitest suites"
	@echo "  make docker-up         - Build and start DB, migrations, app, and worker"

setup: install frontend-install env

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install pytest pytest-asyncio httpx aiosqlite ruff

env:
	@test -f .env || cp .env.example .env

migrate:
	$(ALEMBIC) upgrade head

run:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

worker:
	$(PYTHON) -m app.worker

run-prod:
	$(GUNICORN) app.main:app --workers $${WORKERS:-2} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$${PORT:-8000}

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm test

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-build:
	cd frontend && npm run build

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

test:
	TESTING=true \
	DATABASE_URL=sqlite+aiosqlite:///:memory: \
	WEBHOOK_SECRET=test-webhook-secret-key-at-least-32-characters \
	SESSION_SECRET=test-session-secret-key-at-least-32-characters \
	ADMIN_USERNAME=admin \
	ADMIN_PASSWORD_HASH='$$2b$$12$$i/bda5DB0i74vSubiIswMe6rBh9Ft4wVxieTuJbTo.PgMYHvzovC.' \
	$(PYTEST) -v
	cd frontend && npm test

test-cov:
	$(PYTEST) --cov=app --cov-report=term-missing

lint:
	$(VENV)/bin/ruff check app tests

format:
	$(VENV)/bin/ruff format app tests

type-check:
	cd frontend && npm run typecheck

db-reset:
	rm -f acquiremock.db
	$(ALEMBIC) upgrade head

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage

health:
	curl -sf http://localhost:$${PORT:-8000}/health

quick-start: env migrate run
