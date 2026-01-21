"""
Model promotion script for CI/CD pipeline.
Promotes ML models through stages: None -> Staging -> Production
"""
import argparse
import os
import sys
from datetime import datetime

try:
    import mlflow
    from mlflow.tracking import MlflowClient
except ImportError:
    print("MLflow not installed. Run: pip install mlflow")
    sys.exit(1)


def get_client():
    """Initialize MLflow client."""
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    mlflow.set_tracking_uri(tracking_uri)
    return MlflowClient()


def get_latest_model_version(client, model_name: str, stage: str = None):
    """Get the latest version of a model, optionally filtered by stage."""
    versions = client.search_model_versions(f"name='{model_name}'")
    
    if stage:
        versions = [v for v in versions if v.current_stage == stage]
    
    if not versions:
        return None
    
    # Sort by version number (descending)
    versions.sort(key=lambda x: int(x.version), reverse=True)
    return versions[0]


def promote_model(model_name: str, target_stage: str, version: int = None):
    """Promote a model to the specified stage."""
    client = get_client()
    
    valid_stages = ["Staging", "Production", "Archived"]
    if target_stage not in valid_stages:
        print(f"Invalid stage: {target_stage}. Must be one of: {valid_stages}")
        sys.exit(1)
    
    # Get version to promote
    if version:
        model_version = client.get_model_version(model_name, version)
    else:
        # Get latest version from previous stage
        if target_stage == "Staging":
            model_version = get_latest_model_version(client, model_name, stage="None")
        elif target_stage == "Production":
            model_version = get_latest_model_version(client, model_name, stage="Staging")
        else:
            model_version = get_latest_model_version(client, model_name)
    
    if not model_version:
        print(f"No model version found for {model_name}")
        sys.exit(1)
    
    print(f"Promoting {model_name} v{model_version.version} to {target_stage}")
    print(f"  Current stage: {model_version.current_stage}")
    print(f"  Run ID: {model_version.run_id}")
    
    # Transition the model
    client.transition_model_version_stage(
        name=model_name,
        version=model_version.version,
        stage=target_stage,
        archive_existing_versions=(target_stage == "Production"),
    )
    
    # Add description
    timestamp = datetime.now().isoformat()
    client.update_model_version(
        name=model_name,
        version=model_version.version,
        description=f"Promoted to {target_stage} at {timestamp}",
    )
    
    print(f"✅ Successfully promoted to {target_stage}")
    return model_version.version


def validate_model(model_name: str, version: int):
    """Run validation checks on a model before promotion."""
    client = get_client()
    
    model_version = client.get_model_version(model_name, version)
    run = client.get_run(model_version.run_id)
    
    checks = {
        "has_metrics": len(run.data.metrics) > 0,
        "has_params": len(run.data.params) > 0,
        "not_archived": model_version.current_stage != "Archived",
    }
    
    # Check minimum performance thresholds
    metrics = run.data.metrics
    if "rmse" in metrics:
        checks["rmse_threshold"] = metrics["rmse"] < 100  # Adjust threshold
    if "mape" in metrics:
        checks["mape_threshold"] = metrics["mape"] < 50  # Adjust threshold
    
    print(f"\nValidation results for {model_name} v{version}:")
    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False
    
    return all_passed


def list_models(model_name: str = None):
    """List all registered models and their versions."""
    client = get_client()
    
    if model_name:
        versions = client.search_model_versions(f"name='{model_name}'")
        print(f"\nVersions of {model_name}:")
        for v in sorted(versions, key=lambda x: int(x.version)):
            print(f"  v{v.version}: {v.current_stage} (run: {v.run_id[:8]})")
    else:
        models = client.search_registered_models()
        print("\nRegistered models:")
        for m in models:
            latest = get_latest_model_version(client, m.name)
            print(f"  {m.name}: latest v{latest.version if latest else 'N/A'}")


def main():
    parser = argparse.ArgumentParser(description="MLflow Model Promotion Tool")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Promote command
    promote_parser = subparsers.add_parser("promote", help="Promote a model")
    promote_parser.add_argument("--model", required=True, help="Model name")
    promote_parser.add_argument("--stage", required=True, help="Target stage")
    promote_parser.add_argument("--version", type=int, help="Specific version")
    promote_parser.add_argument("--validate", action="store_true", help="Validate first")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a model")
    validate_parser.add_argument("--model", required=True, help="Model name")
    validate_parser.add_argument("--version", type=int, required=True, help="Version")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List models")
    list_parser.add_argument("--model", help="Specific model name")
    
    args = parser.parse_args()
    
    if args.command == "promote":
        if args.validate:
            version = args.version or get_latest_model_version(
                get_client(), args.model
            ).version
            if not validate_model(args.model, version):
                print("❌ Validation failed. Aborting promotion.")
                sys.exit(1)
        promote_model(args.model, args.stage, args.version)
    
    elif args.command == "validate":
        success = validate_model(args.model, args.version)
        sys.exit(0 if success else 1)
    
    elif args.command == "list":
        list_models(args.model)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
