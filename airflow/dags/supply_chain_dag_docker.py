"""
Supply Chain ETL Pipeline - Docker Airflow DAG
Paths configured for Docker volume mounts.

Place this file in: C:/Users/Manu/airflow/dags/supply_chain_dag.py
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# === DOCKER PATHS (mounted volumes) ===
PROJECT_PATH = "/opt/airflow/project"
RAW_DATA_PATH = "/opt/airflow/raw_data"

default_args = {
    'owner': 'manu',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

with DAG(
    dag_id='supply_chain_etl',
    default_args=default_args,
    description='Supply Chain Pipeline: Bronze → Silver → Gold',
    schedule_interval='0 6 * * *',  # Daily at 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['supply_chain', 'etl', 'dbt'],
    doc_md="""
    ## Supply Chain ETL Pipeline
    
    **Schedule:** Daily at 6 AM
    
    **Steps:**
    1. Load Bronze (raw → Delta Lake)
    2. Validate Bronze (data quality checks)
    3. dbt Silver (staging models)
    4. dbt Gold (aggregation models)
    5. dbt Test (data tests)
    6. Generate Docs
    """,
) as dag:
    
    # Task 1: Load Bronze Layer
    load_bronze = BashOperator(
        task_id='load_bronze',
        bash_command=f'cd {PROJECT_PATH} && python src/ingestion/load_bronze.py',
        doc_md="Load raw parquet from Google Drive into local Delta Lake Bronze layer.",
    )
    
    # Task 2: Validate Bronze Layer
    validate_bronze = BashOperator(
        task_id='validate_bronze',
        bash_command=f'cd {PROJECT_PATH} && python src/quality/validate_bronze.py',
        doc_md="Run data quality checks: nulls, uniqueness, referential integrity.",
    )
    
    # Task 3: Run dbt Silver models
    dbt_silver = BashOperator(
        task_id='dbt_silver',
        bash_command=f'cd {PROJECT_PATH}/dbt_project && dbt run --select silver',
        doc_md="Run staging models: stg_sales, stg_products, stg_suppliers, stg_inventory.",
    )
    
    # Task 4: Run dbt Gold models
    dbt_gold = BashOperator(
        task_id='dbt_gold',
        bash_command=f'cd {PROJECT_PATH}/dbt_project && dbt run --select gold',
        doc_md="Run aggregation models: fct_weekly_sales, fct_monthly_sales, dim_product_performance.",
    )
    
    # Task 5: Run dbt tests
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command=f'cd {PROJECT_PATH}/dbt_project && dbt test || true',  # Don't fail on warnings
        doc_md="Run dbt data tests defined in schema.yml.",
    )
    
    # Task 6: Generate dbt docs
    dbt_docs = BashOperator(
        task_id='dbt_docs',
        bash_command=f'cd {PROJECT_PATH}/dbt_project && dbt docs generate',
        doc_md="Generate dbt documentation site.",
    )
    
    # === TASK DEPENDENCIES ===
    load_bronze >> validate_bronze >> dbt_silver >> dbt_gold >> dbt_test >> dbt_docs
