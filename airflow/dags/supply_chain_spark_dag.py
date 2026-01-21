"""
Supply Chain ETL Pipeline - PySpark Airflow DAG
Runs Bronze → Silver → Gold using PySpark.

Place this file in: C:/Users/Manu/airflow/dags/supply_chain_spark_dag.py
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# === CONFIGURATION ===
PROJECT_PATH = "C:/Users/Manu/supply_chain_project"
SPARK_PATH = f"{PROJECT_PATH}/src/spark"
PYTHON_PATH = f"{PROJECT_PATH}/venv/Scripts/python.exe"

default_args = {
    'owner': 'manu',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),  # Spark can take longer
}

with DAG(
    dag_id='supply_chain_etl_spark',
    default_args=default_args,
    description='Supply Chain Pipeline using PySpark: Bronze → Silver → Gold',
    schedule_interval='0 7 * * *',  # Daily at 7 AM (after dbt DAG)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['supply_chain', 'etl', 'pyspark'],
    doc_md="""
    ## Supply Chain ETL Pipeline (PySpark)
    
    **Parallel implementation to the dbt pipeline.**
    
    **Schedule:** Daily at 7 AM
    
    **Steps:**
    1. Load Bronze (raw → Delta Lake via Spark)
    2. Validate Bronze (data quality checks)
    3. Transform Silver (staging models)
    4. Transform Gold (aggregation models)
    
    **Output:**
    - `data/bronze_spark/` - Raw data as Delta tables
    - `data/silver_spark/` - Cleaned/staged data
    - `data/gold_spark/` - Aggregated analytics tables
    """,
) as dag:
    
    # Task 1: Load Bronze Layer
    load_bronze = BashOperator(
        task_id='load_bronze_spark',
        bash_command=f'{PYTHON_PATH} {SPARK_PATH}/load_bronze_spark.py',
        doc_md="Load raw parquet files into Bronze Delta Lake using PySpark.",
    )
    
    # Task 2: Validate Bronze Layer
    validate_bronze = BashOperator(
        task_id='validate_bronze_spark',
        bash_command=f'{PYTHON_PATH} {SPARK_PATH}/validate_bronze_spark.py || true',
        doc_md="Run data quality checks using PySpark.",
    )
    
    # Task 3: Transform Silver Layer
    transform_silver = BashOperator(
        task_id='transform_silver_spark',
        bash_command=f'{PYTHON_PATH} {SPARK_PATH}/transform_silver_spark.py',
        doc_md="Run Silver transformations: stg_products, stg_suppliers, stg_sales, stg_inventory.",
    )
    
    # Task 4: Transform Gold Layer
    transform_gold = BashOperator(
        task_id='transform_gold_spark',
        bash_command=f'{PYTHON_PATH} {SPARK_PATH}/transform_gold_spark.py',
        doc_md="Run Gold transformations: fct_weekly_sales, fct_monthly_sales, dim_product_performance.",
    )
    
    # === TASK DEPENDENCIES ===
    load_bronze >> validate_bronze >> transform_silver >> transform_gold
