# Airflow Setup Guide

## Prerequisites
- Docker Desktop installed and running
- Your supply_chain_project folder ready

## Quick Start

### 1. Create Airflow folder
```powershell
mkdir C:\Users\Manu\airflow
cd C:\Users\Manu\airflow
mkdir dags logs plugins
```

### 2. Copy files
- Copy `docker-compose-airflow.yaml` → `C:\Users\Manu\airflow\docker-compose.yaml`
- Copy `supply_chain_simple_dag.py` → `C:\Users\Manu\airflow\dags\`

### 3. Start Airflow
```powershell
cd C:\Users\Manu\airflow

# Initialize (first time only)
docker compose up airflow-init

# Start services
docker compose up -d

# Check status
docker compose ps
```

### 4. Access Airflow UI
- Open: http://localhost:8080
- Login: admin / admin

### 5. Run the DAG
1. Find `supply_chain_etl_simple` in the DAG list
2. Toggle ON (enable the DAG)
3. Click "Play" button → "Trigger DAG"
4. Watch the tasks run in Graph view

## DAG Structure

```
load_bronze → validate_bronze → dbt_silver → dbt_gold → dbt_test → dbt_docs
```

## Useful Commands

```powershell
# View logs
docker compose logs airflow-scheduler

# Stop Airflow
docker compose down

# Restart
docker compose restart

# Full reset (delete everything)
docker compose down -v
```

## Troubleshooting

### "Module not found" errors
The docker-compose installs packages automatically. If issues persist:
```bash
docker compose exec airflow-webserver pip install duckdb deltalake dbt-duckdb
```

### Path issues
If DAG can't find your project:
1. Check volume mounts in docker-compose.yaml
2. Verify paths use forward slashes: `/c/Users/Manu/...`

### DAG not showing up
1. Check for Python syntax errors: `python dags/supply_chain_simple_dag.py`
2. Wait 30 seconds for Airflow to detect new DAGs
3. Check scheduler logs: `docker compose logs airflow-scheduler`

## Alternative: WSL Setup (No Docker)

If you prefer running Airflow directly:

```bash
# In WSL (Ubuntu)
pip install apache-airflow==2.8.1

# Initialize
airflow db init
airflow users create --username admin --password admin --firstname A --lastname B --role Admin --email a@b.com

# Start (in separate terminals)
airflow webserver --port 8080
airflow scheduler
```

Copy your DAG to `~/airflow/dags/`
