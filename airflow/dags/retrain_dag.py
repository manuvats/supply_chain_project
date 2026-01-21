"""
Phase 3.4: Airflow Retraining DAG
Monitors drift → Retrains if needed → Registers new model
Place in: airflow/dags/retrain_dag.py
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from pathlib import Path
import subprocess
import json

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
SRC_DIR = PROJECT_ROOT / "src" / "mlops"

default_args = {
    "owner": "manu",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def run_drift_check(**context):
    """Run drift monitoring, push result to XCom."""
    result = subprocess.run(
        ["python", str(SRC_DIR / "drift_monitor.py")],
        capture_output=True,
        text=True
    )
    
    # Check exit code (1 = drift detected)
    drift_detected = result.returncode == 1
    context["ti"].xcom_push(key="drift_detected", value=drift_detected)
    
    print(f"Drift check output:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr:\n{result.stderr}")
    
    return drift_detected


def decide_retrain(**context):
    """Branch based on drift detection."""
    drift_detected = context["ti"].xcom_pull(key="drift_detected", task_ids="check_drift")
    if drift_detected:
        return "retrain_model"
    return "skip_retrain"


def retrain_model(**context):
    """Run model training script."""
    # Use the comparison training script from Phase 2.3
    train_script = PROJECT_ROOT / "src" / "ml" / "train_forecast_comparison.py"
    
    result = subprocess.run(
        ["python", str(train_script)],
        capture_output=True,
        text=True
    )
    
    print(f"Training output:\n{result.stdout}")
    if result.returncode != 0:
        raise Exception(f"Training failed:\n{result.stderr}")
    
    return "Training completed"


def register_new_model(**context):
    """Register best model from latest training run."""
    result = subprocess.run(
        ["python", str(SRC_DIR / "model_registry.py"), "register"],
        capture_output=True,
        text=True
    )
    
    print(f"Registration output:\n{result.stdout}")
    if result.returncode != 0:
        raise Exception(f"Registration failed:\n{result.stderr}")


def promote_to_staging(**context):
    """Promote newly registered model to Staging."""
    # Get latest version (assumes just registered)
    from mlflow.tracking import MlflowClient
    import mlflow
    
    mlflow.set_tracking_uri(f"file:///{PROJECT_ROOT / 'mlruns'}".replace("\\", "/"))
    client = MlflowClient()
    
    versions = client.search_model_versions("name='demand_forecast_model'")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        client.transition_model_version_stage(
            name="demand_forecast_model",
            version=latest.version,
            stage="Staging"
        )
        print(f"✓ Promoted v{latest.version} to Staging")


def notify_completion(**context):
    """Send notification (placeholder - add Slack/email)."""
    drift_detected = context["ti"].xcom_pull(key="drift_detected", task_ids="check_drift")
    
    if drift_detected:
        msg = "✓ Retraining completed, new model in Staging"
    else:
        msg = "✓ No drift detected, skipped retraining"
    
    print(msg)
    # TODO: Add Slack/email notification
    # slack_webhook(msg)


with DAG(
    dag_id="demand_forecast_retrain",
    default_args=default_args,
    description="Monitor drift and retrain demand forecast model",
    schedule_interval="0 6 * * 1",  # Weekly on Monday 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlops", "demand_forecast"],
) as dag:

    start = EmptyOperator(task_id="start")

    check_drift = PythonOperator(
        task_id="check_drift",
        python_callable=run_drift_check,
    )

    branch = BranchPythonOperator(
        task_id="branch_on_drift",
        python_callable=decide_retrain,
    )

    retrain = PythonOperator(
        task_id="retrain_model",
        python_callable=retrain_model,
    )

    skip = EmptyOperator(task_id="skip_retrain")

    register = PythonOperator(
        task_id="register_model",
        python_callable=register_new_model,
    )

    promote = PythonOperator(
        task_id="promote_staging",
        python_callable=promote_to_staging,
    )

    notify = PythonOperator(
        task_id="notify",
        python_callable=notify_completion,
        trigger_rule="none_failed_min_one_success",  # Run regardless of branch
    )

    end = EmptyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    # DAG flow
    start >> check_drift >> branch
    branch >> retrain >> register >> promote >> notify >> end
    branch >> skip >> notify >> end
