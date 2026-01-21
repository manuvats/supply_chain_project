# Quantum Bricks - Makefile
# Common commands for development and CI/CD

.PHONY: help install install-dev lint format test test-unit test-integration test-all coverage clean run serve dbt-run dbt-test docker-build docker-run

# Default target
help:
	@echo "Quantum Bricks - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make install-dev    Install all dependencies (including dev)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linters (ruff, mypy)"
	@echo "  make format         Format code (black, isort)"
	@echo "  make check          Run all checks without modifying files"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-int       Run integration tests only"
	@echo "  make test-dq        Run data quality tests"
	@echo "  make coverage       Run tests with coverage report"
	@echo ""
	@echo "Run:"
	@echo "  make serve          Start FastAPI server"
	@echo "  make dashboard      Start Streamlit dashboard"
	@echo ""
	@echo "dbt:"
	@echo "  make dbt-run        Run dbt models"
	@echo "  make dbt-test       Run dbt tests"
	@echo "  make dbt-docs       Generate and serve dbt docs"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove build artifacts"

# ============================================
# Setup
# ============================================
install:
	pip install -r requirements.txt

install-dev:
	pip install -e ".[dev,llm]"
	pre-commit install

# ============================================
# Code Quality
# ============================================
lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/
	isort src/ tests/
	ruff check src/ tests/ --fix

check:
	black --check src/ tests/
	isort --check-only src/ tests/
	ruff check src/ tests/

# ============================================
# Testing
# ============================================
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v -m "unit or not integration"

test-int:
	pytest tests/integration/ -v -m integration

test-dq:
	pytest tests/data_quality/ -v

test-all:
	pytest tests/ -v --tb=short -n auto

coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# ============================================
# Run Services
# ============================================
serve:
	uvicorn src.serving.api:app --reload --host 0.0.0.0 --port 8000

dashboard:
	streamlit run dashboards/main_dashboard.py

llm-dashboard:
	streamlit run src/llm/llm_dashboard.py

# ============================================
# dbt Commands
# ============================================
dbt-run:
	cd dbt_project && dbt run --profiles-dir .

dbt-test:
	cd dbt_project && dbt test --profiles-dir .

dbt-docs:
	cd dbt_project && dbt docs generate && dbt docs serve

dbt-build:
	cd dbt_project && dbt build --profiles-dir .

# ============================================
# MLflow
# ============================================
mlflow-ui:
	mlflow ui --host 0.0.0.0 --port 5000

# ============================================
# Docker
# ============================================
docker-build:
	docker build -t quantum-bricks:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env quantum-bricks:latest

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

# ============================================
# Airflow (Docker)
# ============================================
airflow-up:
	cd airflow && docker-compose up -d

airflow-down:
	cd airflow && docker-compose down

# ============================================
# Maintenance
# ============================================
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true
	@echo "Cleaned build artifacts"

# ============================================
# Quick Start
# ============================================
quickstart: install-dev
	@echo "✅ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run tests:     make test"
	@echo "  2. Start API:     make serve"
	@echo "  3. Start dashboard: make dashboard"
