.PHONY: help setup install test run docker-up docker-down docker-logs clean lint format db-reset

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(CYAN)AcquireMock - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

# Setup & Installation
setup: ## Initial setup (create venv and install dependencies)
	@echo "$(CYAN)Creating virtual environment...$(NC)"
	python3 -m venv venv
	@echo "$(GREEN)✓ Virtual environment created$(NC)"
	@echo "$(YELLOW)Activate it with: source venv/bin/activate$(NC)"
	@echo "$(YELLOW)Then run: make install$(NC)"

install: ## Install dependencies
	@echo "$(CYAN)Installing dependencies...$(NC)"
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-dev: ## Install development dependencies
	@echo "$(CYAN)Installing dev dependencies...$(NC)"
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black flake8 mypy
	@echo "$(GREEN)✓ Dev dependencies installed$(NC)"

# Running the application
run: ## Run the application locally
	@echo "$(CYAN)Starting AcquireMock...$(NC)"
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

run-prod: ## Run in production mode (no reload)
	@echo "$(CYAN)Starting AcquireMock (production)...$(NC)"
	gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Docker commands
docker-up: ## Start with Docker Compose
	@echo "$(CYAN)Starting Docker containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Containers started$(NC)"
	@echo "$(YELLOW)Access at: http://localhost:8000$(NC)"
	@echo "$(YELLOW)View logs: make docker-logs$(NC)"

docker-down: ## Stop Docker containers
	@echo "$(CYAN)Stopping Docker containers...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Containers stopped$(NC)"

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-rebuild: ## Rebuild and restart Docker containers
	@echo "$(CYAN)Rebuilding Docker containers...$(NC)"
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "$(GREEN)✓ Containers rebuilt and started$(NC)"

docker-clean: ## Remove Docker containers and volumes
	@echo "$(CYAN)Cleaning up Docker...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Docker cleanup complete$(NC)"

# Testing
test: ## Run tests
	@echo "$(CYAN)Running tests...$(NC)"
	pytest tests/ -v

test-cov: ## Run tests with coverage
	@echo "$(CYAN)Running tests with coverage...$(NC)"
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

test-integration: ## Run integration tests (requires running server)
	@echo "$(CYAN)Running integration tests...$(NC)"
	python scripts/manual_payment_test.py

# Code Quality
lint: ## Run linters (flake8)
	@echo "$(CYAN)Running linter...$(NC)"
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format: ## Format code with black
	@echo "$(CYAN)Formatting code...$(NC)"
	black .
	@echo "$(GREEN)✓ Code formatted$(NC)"

format-check: ## Check if code is formatted
	@echo "$(CYAN)Checking code formatting...$(NC)"
	black --check .

type-check: ## Run type checker (mypy)
	@echo "$(CYAN)Running type checker...$(NC)"
	mypy . --ignore-missing-imports

# Database
db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(RED)⚠️  WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f *.db *.sqlite *.sqlite3; \
		echo "$(GREEN)✓ Database reset$(NC)"; \
	else \
		echo "$(YELLOW)Database reset cancelled$(NC)"; \
	fi

# Cleanup
clean: ## Clean temporary files
	@echo "$(CYAN)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean docker-clean ## Clean everything including Docker

# Environment
env: ## Copy .env.example to .env
	@if [ -f .env ]; then \
		echo "$(YELLOW)⚠️  .env already exists$(NC)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env created from .env.example$(NC)"; \
		echo "$(YELLOW)⚠️  Edit .env and set your configuration$(NC)"; \
	fi

# Health check
health: ## Check if the service is healthy
	@echo "$(CYAN)Checking service health...$(NC)"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "$(RED)✗ Service is not running$(NC)"

# Documentation
docs: ## Open documentation
	@echo "$(CYAN)Opening documentation...$(NC)"
	@if command -v xdg-open > /dev/null; then \
		xdg-open http://localhost:8000/docs; \
	elif command -v open > /dev/null; then \
		open http://localhost:8000/docs; \
	else \
		echo "$(YELLOW)Open http://localhost:8000/docs in your browser$(NC)"; \
	fi

# All-in-one commands
all: clean install test lint ## Clean, install, test, and lint

dev: setup install-dev env ## Full development setup
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "$(YELLOW)Activate venv: source venv/bin/activate$(NC)"
	@echo "$(YELLOW)Run server: make run$(NC)"

quick-start: env docker-up ## Quick start with Docker (recommended)
	@echo ""
	@echo "$(GREEN)✓ AcquireMock is running!$(NC)"
	@echo ""
	@echo "$(CYAN)Access points:$(NC)"
	@echo "  • Application: $(YELLOW)http://localhost:8000$(NC)"
	@echo "  • Test Page:   $(YELLOW)http://localhost:8000/test$(NC)"
	@echo "  • API Docs:    $(YELLOW)http://localhost:8000/docs$(NC)"
	@echo "  • Health:      $(YELLOW)http://localhost:8000/health$(NC)"
	@echo ""
	@echo "$(CYAN)Useful commands:$(NC)"
	@echo "  • View logs:  $(YELLOW)make docker-logs$(NC)"
	@echo "  • Stop:       $(YELLOW)make docker-down$(NC)"
	@echo "  • Restart:    $(YELLOW)make docker-rebuild$(NC)"
	@echo ""

# CI/CD helpers
ci-test: install-dev test lint type-check ## Run all CI checks
	@echo "$(GREEN)✓ All CI checks passed$(NC)"

# Version info
version: ## Show version information
	@echo "$(CYAN)AcquireMock Version Information$(NC)"
	@python -c "import sys; print(f'Python: {sys.version}')"
	@pip show fastapi | grep Version || echo "FastAPI not installed"
	@docker --version 2>/dev/null || echo "Docker not installed"
	@docker-compose --version 2>/dev/null || echo "Docker Compose not installed"