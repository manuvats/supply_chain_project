# Phase 6: CI/CD Automation

## Overview

This phase implements a complete CI/CD pipeline for the Quantum Bricks supply chain project using GitHub Actions, pytest, and Docker.

## Components

### 1. Test Suite (`tests/`)

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_features.py     # Feature engineering tests
│   ├── test_anomaly.py      # Anomaly detection tests
│   ├── test_ml.py           # ML model tests
│   └── test_llm.py          # LLM component tests
├── integration/
│   └── test_pipeline.py     # End-to-end pipeline tests
└── data_quality/
    └── test_data_validation.py  # Data quality tests
```

### 2. GitHub Actions Workflows (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR to main/develop | Lint, test, validate |
| `cd.yml` | Push to main, tags | Build, deploy to staging/production |

### 3. Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project config, tool settings |
| `Makefile` | Common commands |
| `.pre-commit-config.yaml` | Pre-commit hooks |
| `Dockerfile` | Container build |

## Quick Start

```bash
# 1. Install dev dependencies
make install-dev

# 2. Run all tests
make test

# 3. Run with coverage
make coverage

# 4. Run linters
make lint

# 5. Format code
make format
```

## CI Pipeline Stages

```
┌─────────┐    ┌────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Lint   │───▶│ Unit Tests │───▶│ Data Quality │───▶│ Integration     │
└─────────┘    └────────────┘    └──────────────┘    └─────────────────┘
                                                              │
                                                              ▼
┌─────────────┐    ┌─────────────────┐    ┌───────────────────────────┐
│  dbt Tests  │───▶│ Build Validate  │───▶│ CI Summary                │
└─────────────┘    └─────────────────┘    └───────────────────────────┘
```

## CD Pipeline Stages

```
┌──────────┐    ┌───────────────┐    ┌─────────────────┐    ┌────────────────┐
│ CI Check │───▶│ Build Docker  │───▶│ Deploy Staging  │───▶│ Deploy Prod    │
└──────────┘    └───────────────┘    └─────────────────┘    └────────────────┘
```

## Test Categories

### Unit Tests
- Feature engineering logic
- Anomaly detection algorithms
- ML metrics and utilities
- LLM component validation

### Integration Tests
- Bronze → Silver → Gold data flow
- API endpoint validation
- dbt model dependencies

### Data Quality Tests
- Completeness checks
- Value range validation
- Consistency rules
- Freshness checks

## Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v -m integration

# Data quality tests
pytest tests/data_quality/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Parallel execution
pytest tests/ -n auto
```

## Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

Hooks included:
- Black (formatting)
- isort (import sorting)
- Ruff (linting)
- Bandit (security)
- Hadolint (Dockerfile)

## Model Promotion

```bash
# List models
python scripts/promote_model.py list

# Promote to staging
python scripts/promote_model.py promote --model demand_forecast --stage Staging

# Promote to production (with validation)
python scripts/promote_model.py promote --model demand_forecast --stage Production --validate
```

## Docker

```bash
# Build image
make docker-build

# Run container
make docker-run

# Or with docker-compose
docker-compose up -d
```

## Environment Variables

Create `.env` file:

```env
# MLflow
MLFLOW_TRACKING_URI=sqlite:///mlflow.db

# LLM (optional)
GROQ_API_KEY=your-key

# Database
DUCKDB_PATH=data/warehouse.duckdb
```

## GitHub Secrets Required

For CI/CD to work, add these secrets to your GitHub repository:

| Secret | Purpose |
|--------|---------|
| `MLFLOW_TRACKING_URI` | MLflow tracking server |
| `GROQ_API_KEY` | LLM API (optional) |
| `SLACK_WEBHOOK` | Deployment notifications (optional) |

## File Placement

Copy these files to your project:

```
C:\Users\Manu\supply_chain_project\
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── data_quality/
├── scripts/
│   └── promote_model.py
├── .pre-commit-config.yaml
├── pyproject.toml
├── Makefile
├── Dockerfile
└── requirements-ci.txt
```

## Customization

1. **Adjust test thresholds** in `tests/unit/test_ml.py`
2. **Modify CI stages** in `.github/workflows/ci.yml`
3. **Configure deployment targets** in `.github/workflows/cd.yml`
4. **Update linting rules** in `pyproject.toml`
