"""
Demand Forecast Inference
Auto-selects best model from comparison results, generates predictions → DuckDB
"""
import pandas as pd
import numpy as np
import duckdb
import joblib
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
MODELS_DIR = PROJECT_ROOT / "models"

FEATURE_COLS = [
    "day_of_week", "day_of_year", "month", "is_promo",
    "lag_7", "lag_14", "lag_30",
    "rolling_mean_7", "rolling_std_7",
    "rolling_mean_14", "rolling_std_14",
    "rolling_mean_30", "rolling_std_30",
]


def get_best_model(metric="wape"):
    """
    Read comparison results and return best ML model.
    Only considers ML models (XGBoost, LightGBM) since TS models predict aggregated.
    """
    comparison_file = MODELS_DIR / "model_comparison_all_items.csv"
    
    if not comparison_file.exists():
        print(f"  Warning: {comparison_file} not found. Defaulting to LightGBM.")
        return "lightgbm", MODELS_DIR / "lightgbm_demand.joblib", None
    
    df = pd.read_csv(comparison_file)
    
    # Filter to ML models only (they predict at SKU-store-day level)
    ml_models = df[df["Type"] == "ML"].copy()
    
    if len(ml_models) == 0:
        print("  Warning: No ML models found in comparison. Defaulting to LightGBM.")
        return "lightgbm", MODELS_DIR / "lightgbm_demand.joblib", None
    
    # Select best by metric (lower is better for wape, mae, rmse)
    if metric in ["wape", "mae", "rmse", "mase"]:
        best_row = ml_models.loc[ml_models[metric].idxmin()]
    else:  # higher is better (hit_rate)
        best_row = ml_models.loc[ml_models[metric].idxmax()]
    
    model_name = best_row["Model"].lower()
    model_path = MODELS_DIR / f"{model_name}_demand.joblib"
    
    return model_name, model_path, best_row


def load_model(model_path):
    """Load trained model."""
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    return joblib.load(model_path)


def get_available_features(df):
    """Return only features that exist in dataframe."""
    return [c for c in FEATURE_COLS if c in df.columns]


def predict(model, df: pd.DataFrame) -> pd.DataFrame:
    """Add predictions to dataframe."""
    available_features = get_available_features(df)
    
    if "is_promo" in df.columns:
        df["is_promo"] = df["is_promo"].astype(int)
    
    # Handle missing features
    X = df[available_features].copy()
    
    # Predict
    df["predicted_demand"] = model.predict(X)
    df["prediction_error"] = df["units_sold"] - df["predicted_demand"]
    df["prediction_error_pct"] = (df["prediction_error"] / df["units_sold"].replace(0, np.nan)) * 100
    
    return df


def save_predictions(df: pd.DataFrame, model_name: str, con: duckdb.DuckDBPyConnection):
    """Save predictions to DuckDB with metadata."""
    con.execute("CREATE SCHEMA IF NOT EXISTS main_predictions")
    con.execute("DROP TABLE IF EXISTS main_predictions.demand_forecast")
    
    # Add metadata
    df["model_used"] = model_name
    df["predicted_at"] = datetime.now()
    
    con.register("pred_df", df)
    con.execute("""
        CREATE TABLE main_predictions.demand_forecast AS 
        SELECT * FROM pred_df
    """)
    print(f"  Saved {len(df):,} predictions to main_predictions.demand_forecast")


def main(model_name: str = None, metric: str = "wape"):
    """
    Run inference pipeline.
    
    Args:
        model_name: Specify model ('xgboost', 'lightgbm') or None for auto-select
        metric: Metric to use for auto-selection ('wape', 'mae', 'hit_rate_20')
    """
    print("Demand Forecast Inference")
    print("=" * 50)
    
    con = duckdb.connect(str(DB_PATH))
    
    # Model selection
    if model_name:
        model_path = MODELS_DIR / f"{model_name.lower()}_demand.joblib"
        print(f"Using specified model: {model_name}")
        best_row = None
    else:
        model_name, model_path, best_row = get_best_model(metric)
        print(f"Auto-selected best model by {metric}: {model_name.upper()}")
        if best_row is not None:
            print(f"  WAPE: {best_row['wape']:.1f}%, Bias: {best_row['bias']:+.1f}%")
    
    print(f"\nLoading model from: {model_path}")
    model = load_model(model_path)
    
    print("Loading features...")
    df = con.execute("SELECT * FROM main_features.demand_features ORDER BY ds").df()
    available_features = get_available_features(df)
    df = df.dropna(subset=available_features)
    print(f"  Rows: {len(df):,}")
    print(f"  Features used: {available_features}")
    
    print("\nGenerating predictions...")
    df = predict(model, df)
    
    print("\nSaving to DuckDB...")
    save_predictions(df, model_name, con)
    
    # Quick stats
    wape = np.abs(df["prediction_error"]).sum() / df["units_sold"].sum() * 100
    bias = (df["predicted_demand"].sum() - df["units_sold"].sum()) / df["units_sold"].sum() * 100
    print(f"\nPrediction Stats:")
    print(f"  WAPE: {wape:.2f}%")
    print(f"  Bias: {bias:+.2f}%")
    
    con.close()
    print("\nDone!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate demand forecasts")
    parser.add_argument("--model", choices=["xgboost", "lightgbm"], 
                        help="Model to use (default: auto-select best)")
    parser.add_argument("--metric", default="wape",
                        choices=["wape", "mae", "rmse", "hit_rate_20"],
                        help="Metric for auto-selection (default: wape)")
    
    args = parser.parse_args()
    main(model_name=args.model, metric=args.metric)
