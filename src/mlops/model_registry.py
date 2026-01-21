"""
Phase 3.1: Model Registry Management
Register, promote, and manage model lifecycle via MLflow
"""
import mlflow
from mlflow.tracking import MlflowClient
from pathlib import Path
import argparse

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
MLFLOW_URI = f"file:///{PROJECT_ROOT / 'mlruns'}".replace("\\", "/")
MODEL_NAME = "demand_forecast_model"


def setup_mlflow():
    mlflow.set_tracking_uri(MLFLOW_URI)
    return MlflowClient()


def get_best_run(client: MlflowClient, experiment_name: str = "demand_forecast_comparison", metric: str = "wape"):
    """Find run with lowest MAPE."""
    exp = client.get_experiment_by_name(experiment_name)
    if not exp:
        raise ValueError(f"Experiment '{experiment_name}' not found")
    
    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        order_by=[f"metrics.{metric} ASC"],
        max_results=1
    )
    if not runs:
        raise ValueError("No runs found")
    return runs[0]


def register_model(client: MlflowClient, run_id: str, model_name: str = MODEL_NAME):
    """Register model from run to registry."""
    model_uri = f"runs:/{run_id}/model"
    result = mlflow.register_model(model_uri, model_name)
    print(f"✓ Registered {model_name} version {result.version}")
    return result.version


def promote_model(client: MlflowClient, model_name: str, version: int, stage: str):
    """Promote model to Staging or Production."""
    valid_stages = ["Staging", "Production", "Archived", "None"]
    if stage not in valid_stages:
        raise ValueError(f"Stage must be one of {valid_stages}")
    
    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage=stage,
        archive_existing_versions=(stage == "Production")  # Auto-archive old prod
    )
    print(f"✓ {model_name} v{version} → {stage}")


def get_production_model(client: MlflowClient, model_name: str = MODEL_NAME):
    """Get current production model version."""
    versions = client.get_latest_versions(model_name, stages=["Production"])
    return versions[0] if versions else None


def list_versions(client: MlflowClient, model_name: str = MODEL_NAME):
    """List all versions and their stages."""
    print(f"\n{'Version':<10} {'Stage':<15} {'Run ID':<35}")
    print("-" * 60)
    for mv in client.search_model_versions(f"name='{model_name}'"):
        print(f"{mv.version:<10} {mv.current_stage:<15} {mv.run_id:<35}")


def main():
    parser = argparse.ArgumentParser(description="Model Registry Management")
    parser.add_argument("action", choices=["register", "promote", "list", "get-prod"])
    parser.add_argument("--version", "-v", type=int, help="Model version")
    parser.add_argument("--stage", "-s", choices=["Staging", "Production", "Archived"])
    parser.add_argument("--experiment", "-e", default="demand_forecast_comparison")
    args = parser.parse_args()

    client = setup_mlflow()

    if args.action == "register":
        best_run = get_best_run(client, args.experiment)
        print(f"Best run: {best_run.info.run_id} (WAPE: {best_run.data.metrics.get('wape', 0):.4f})")
        register_model(client, best_run.info.run_id)

    elif args.action == "promote":
        if not args.version or not args.stage:
            print("Error: --version and --stage required for promote")
            return
        promote_model(client, MODEL_NAME, args.version, args.stage)

    elif args.action == "list":
        list_versions(client)

    elif args.action == "get-prod":
        prod = get_production_model(client)
        if prod:
            print(f"Production: v{prod.version} (run: {prod.run_id})")
        else:
            print("No production model set")


if __name__ == "__main__":
    main()
