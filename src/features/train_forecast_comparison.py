"""
Phase 2.3: Demand Forecasting - Multi-Model Comparison
Compares: XGBoost, LightGBM, Prophet, SARIMA
"""
import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
from datetime import datetime
from sklearn.metrics import mean_absolute_error, mean_squared_error
import mlflow
import joblib
import warnings
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ML Features (for tree models) - will be filtered to available columns
ML_FEATURES_CANDIDATES = [
    "day_of_week", "day_of_year", "month", "is_promo",
    "lag_7", "lag_14", "lag_30",
    "rolling_mean_7", "rolling_std_7",
    "rolling_mean_14", "rolling_std_14",
    "rolling_mean_30", "rolling_std_30",
]
TARGET = "units_sold"


def get_ml_features(df):
    """Return only features that exist in dataframe."""
    return [c for c in ML_FEATURES_CANDIDATES if c in df.columns]


def load_data():
    """Load and prep data."""
    con = duckdb.connect(str(DB_PATH))
    df = con.execute("SELECT * FROM main_features.demand_features ORDER BY ds").df()
    con.close()
    
    df["ds"] = pd.to_datetime(df["ds"])
    if "is_promo" in df.columns:
        df["is_promo"] = df["is_promo"].astype(int)
    
    # Print available columns for debugging
    print(f"  Columns: {list(df.columns)}")
    return df


def segment_skus(df, min_volume=100, max_cv=1.5, min_nonzero_pct=0.3):
    """
    Segment SKUs into forecastable vs not.
    
    Criteria for 'forecastable' (ML-suitable):
    - Total volume >= min_volume
    - Coefficient of Variation <= max_cv (demand stability)
    - Non-zero days >= min_nonzero_pct (not too intermittent)
    """
    sku_stats = df.groupby("sku").agg(
        total_volume=(TARGET, "sum"),
        mean_demand=(TARGET, "mean"),
        std_demand=(TARGET, "std"),
        n_days=(TARGET, "count"),
        nonzero_days=(TARGET, lambda x: (x > 0).sum())
    ).reset_index()
    
    # Coefficient of Variation (CV = std/mean)
    sku_stats["cv"] = sku_stats["std_demand"] / sku_stats["mean_demand"].replace(0, np.nan)
    sku_stats["nonzero_pct"] = sku_stats["nonzero_days"] / sku_stats["n_days"]
    
    # Classify
    sku_stats["forecastable"] = (
        (sku_stats["total_volume"] >= min_volume) &
        (sku_stats["cv"] <= max_cv) &
        (sku_stats["nonzero_pct"] >= min_nonzero_pct)
    )
    
    # ABC classification by volume
    sku_stats = sku_stats.sort_values("total_volume", ascending=False)
    sku_stats["cumulative_pct"] = sku_stats["total_volume"].cumsum() / sku_stats["total_volume"].sum()
    sku_stats["abc_class"] = pd.cut(
        sku_stats["cumulative_pct"],
        bins=[0, 0.7, 0.9, 1.0],
        labels=["A", "B", "C"]
    )
    
    return sku_stats


def segment_stores(df, min_volume=500, max_cv=1.5, min_nonzero_pct=0.3):
    """Segment stores into forecastable vs not."""
    store_stats = df.groupby("store_id").agg(
        total_volume=(TARGET, "sum"),
        mean_demand=(TARGET, "mean"),
        std_demand=(TARGET, "std"),
        n_days=(TARGET, "count"),
        nonzero_days=(TARGET, lambda x: (x > 0).sum())
    ).reset_index()
    
    store_stats["cv"] = store_stats["std_demand"] / store_stats["mean_demand"].replace(0, np.nan)
    store_stats["nonzero_pct"] = store_stats["nonzero_days"] / store_stats["n_days"]
    
    store_stats["forecastable"] = (
        (store_stats["total_volume"] >= min_volume) &
        (store_stats["cv"] <= max_cv) &
        (store_stats["nonzero_pct"] >= min_nonzero_pct)
    )
    
    return store_stats


def calc_metrics(y_true, y_pred):
    """Calculate comprehensive forecasting metrics."""
    y_true = pd.Series(y_true).reset_index(drop=True)
    y_pred = pd.Series(y_pred).reset_index(drop=True)
    
    # Basic
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    # WAPE: Weighted Absolute Percentage Error (most useful for demand)
    # Interpretation: "We missed X% of total demand"
    total_actual = y_true.sum()
    wape = (np.abs(y_true - y_pred).sum() / total_actual * 100) if total_actual > 0 else np.nan
    
    # Bias: Positive = over-forecasting, Negative = under-forecasting
    # Interpretation: "We over/under predicted by X% of total demand"
    bias = ((y_pred.sum() - y_true.sum()) / total_actual * 100) if total_actual > 0 else np.nan
    
    # MASE: Mean Absolute Scaled Error (vs naive forecast of previous value)
    # <1 means better than naive, >1 means worse than naive
    naive_errors = np.abs(y_true.diff().dropna())
    mase = mae / naive_errors.mean() if naive_errors.mean() > 0 else np.nan
    
    # Hit Rate: % of predictions within ±20% of actual
    mask = y_true > 0
    if mask.sum() > 0:
        pct_error = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
        hit_rate_20 = (pct_error <= 0.20).mean() * 100
        hit_rate_10 = (pct_error <= 0.10).mean() * 100
    else:
        hit_rate_20 = hit_rate_10 = np.nan
    
    # sMAPE: Symmetric MAPE (bounded 0-200%, handles zeros better)
    denominator = np.abs(y_true) + np.abs(y_pred)
    mask = denominator > 0
    if mask.sum() > 0:
        smape = (2 * np.abs(y_true[mask] - y_pred[mask]) / denominator[mask]).mean() * 100
    else:
        smape = np.nan
    
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape": round(wape, 2),          # Most important for demand
        "bias": round(bias, 2),           # Over/under forecasting
        "mase": round(mase, 3),           # vs naive (< 1 is good)
        "hit_rate_20": round(hit_rate_20, 1),  # % within ±20%
        "hit_rate_10": round(hit_rate_10, 1),  # % within ±10%
        "smape": round(smape, 2),
    }


def calc_metrics_by_group(pred_df, group_col, segment_df=None):
    """Calculate metrics for each group (SKU or Store), with segmentation."""
    results = []
    for name, grp in pred_df.groupby(group_col):
        if len(grp) < 5:  # Skip groups with too few samples
            continue
        m = calc_metrics(grp["actual"], grp["pred"])
        m[group_col] = name
        m["n_records"] = len(grp)
        m["total_actual"] = grp["actual"].sum()
        
        # Add segmentation info if available
        if segment_df is not None and group_col in segment_df.columns:
            seg_row = segment_df[segment_df[group_col] == name]
            if len(seg_row) > 0:
                m["forecastable"] = seg_row["forecastable"].values[0]
                m["cv"] = round(seg_row["cv"].values[0], 2) if not pd.isna(seg_row["cv"].values[0]) else np.nan
                if "abc_class" in seg_row.columns:
                    m["abc_class"] = seg_row["abc_class"].values[0]
        
        results.append(m)
    
    df = pd.DataFrame(results)
    # Reorder columns
    base_cols = [group_col, "n_records", "total_actual"]
    seg_cols = ["forecastable", "abc_class", "cv"] if segment_df is not None else []
    metric_cols = ["wape", "bias", "mase", "hit_rate_20", "mae", "rmse"]
    cols = base_cols + [c for c in seg_cols if c in df.columns] + metric_cols
    return df[[c for c in cols if c in df.columns]]


def train_xgboost(train_df, test_df, sku_segments=None, store_segments=None):
    """XGBoost Regressor - returns aggregated and granular breakdowns."""
    import xgboost as xgb
    
    ml_features = get_ml_features(train_df)
    X_train = train_df[ml_features].dropna()
    y_train = train_df.loc[X_train.index, TARGET]
    X_test = test_df[ml_features].dropna()
    y_test = test_df.loc[X_test.index, TARGET]
    test_dates = test_df.loc[X_test.index, "ds"]
    test_skus = test_df.loc[X_test.index, "sku"]
    test_stores = test_df.loc[X_test.index, "store_id"]
    
    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    y_pred = model.predict(X_test)
    
    # Build prediction dataframe
    pred_df = pd.DataFrame({
        "ds": test_dates.values,
        "sku": test_skus.values,
        "store_id": test_stores.values,
        "actual": y_test.values,
        "pred": y_pred
    })
    
    # Add forecastable flag to predictions
    if sku_segments is not None:
        forecastable_skus = set(sku_segments[sku_segments["forecastable"]]["sku"])
        pred_df["sku_forecastable"] = pred_df["sku"].isin(forecastable_skus)
    else:
        pred_df["sku_forecastable"] = True
    
    # Aggregated metrics - ALL
    daily_all = pred_df.groupby("ds").agg({"actual": "sum", "pred": "sum"}).reset_index()
    agg_metrics_all = calc_metrics(daily_all["actual"], daily_all["pred"])
    
    # Aggregated metrics - FORECASTABLE ONLY
    pred_forecastable = pred_df[pred_df["sku_forecastable"]]
    daily_forecastable = pred_forecastable.groupby("ds").agg({"actual": "sum", "pred": "sum"}).reset_index()
    agg_metrics_forecastable = calc_metrics(daily_forecastable["actual"], daily_forecastable["pred"])
    
    # Granular breakdowns with segmentation
    granular = {
        "by_sku": calc_metrics_by_group(pred_df, "sku", sku_segments),
        "by_store": calc_metrics_by_group(pred_df, "store_id", store_segments),
    }
    
    joblib.dump(model, MODELS_DIR / "xgboost_demand.joblib")
    return {
        "all": agg_metrics_all,
        "forecastable": agg_metrics_forecastable,
        "n_forecastable_skus": pred_df["sku_forecastable"].sum(),
        "n_total_records": len(pred_df),
    }, granular, model


def train_lightgbm(train_df, test_df, sku_segments=None, store_segments=None):
    """LightGBM Regressor - returns aggregated and granular breakdowns."""
    import lightgbm as lgb
    
    ml_features = get_ml_features(train_df)
    X_train = train_df[ml_features].dropna()
    y_train = train_df.loc[X_train.index, TARGET]
    X_test = test_df[ml_features].dropna()
    y_test = test_df.loc[X_test.index, TARGET]
    test_dates = test_df.loc[X_test.index, "ds"]
    test_skus = test_df.loc[X_test.index, "sku"]
    test_stores = test_df.loc[X_test.index, "store_id"]
    
    model = lgb.LGBMRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
    
    y_pred = model.predict(X_test)
    
    # Build prediction dataframe
    pred_df = pd.DataFrame({
        "ds": test_dates.values,
        "sku": test_skus.values,
        "store_id": test_stores.values,
        "actual": y_test.values,
        "pred": y_pred
    })
    
    # Add forecastable flag to predictions
    if sku_segments is not None:
        forecastable_skus = set(sku_segments[sku_segments["forecastable"]]["sku"])
        pred_df["sku_forecastable"] = pred_df["sku"].isin(forecastable_skus)
    else:
        pred_df["sku_forecastable"] = True
    
    # Aggregated metrics - ALL
    daily_all = pred_df.groupby("ds").agg({"actual": "sum", "pred": "sum"}).reset_index()
    agg_metrics_all = calc_metrics(daily_all["actual"], daily_all["pred"])
    
    # Aggregated metrics - FORECASTABLE ONLY
    pred_forecastable = pred_df[pred_df["sku_forecastable"]]
    daily_forecastable = pred_forecastable.groupby("ds").agg({"actual": "sum", "pred": "sum"}).reset_index()
    agg_metrics_forecastable = calc_metrics(daily_forecastable["actual"], daily_forecastable["pred"])
    
    # Granular breakdowns with segmentation
    granular = {
        "by_sku": calc_metrics_by_group(pred_df, "sku", sku_segments),
        "by_store": calc_metrics_by_group(pred_df, "store_id", store_segments),
    }
    
    joblib.dump(model, MODELS_DIR / "lightgbm_demand.joblib")
    return {
        "all": agg_metrics_all,
        "forecastable": agg_metrics_forecastable,
        "n_forecastable_skus": pred_df["sku_forecastable"].sum(),
        "n_total_records": len(pred_df),
    }, granular, model


def train_prophet(train_df, test_df):
    """Facebook Prophet - aggregated daily demand."""
    from prophet import Prophet
    
    # Prophet needs aggregated time series (ds, y)
    train_agg = train_df.groupby("ds")[TARGET].sum().reset_index()
    train_agg.columns = ["ds", "y"]
    
    test_agg = test_df.groupby("ds")[TARGET].sum().reset_index()
    test_agg.columns = ["ds", "y"]
    
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        seasonality_mode="multiplicative"
    )
    model.fit(train_agg)
    
    forecast = model.predict(test_agg[["ds"]])
    y_pred = forecast["yhat"].values
    y_true = test_agg["y"].values
    
    metrics = calc_metrics(pd.Series(y_true), pd.Series(y_pred))
    
    joblib.dump(model, MODELS_DIR / "prophet_demand.joblib")
    return metrics, model


def train_sarima(train_df, test_df):
    """SARIMA - aggregated daily demand."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    
    # Aggregate to daily
    train_agg = train_df.groupby("ds")[TARGET].sum()
    test_agg = test_df.groupby("ds")[TARGET].sum()
    
    # SARIMA(1,1,1)(1,1,1,7) - weekly seasonality
    model = SARIMAX(
        train_agg,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 7),
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    fitted = model.fit(disp=False)
    
    # Forecast
    y_pred = fitted.forecast(steps=len(test_agg))
    y_true = test_agg.values
    
    metrics = calc_metrics(pd.Series(y_true), pd.Series(y_pred.values))
    
    joblib.dump(fitted, MODELS_DIR / "sarima_demand.joblib")
    return metrics, fitted


def train_ets(train_df, test_df):
    """Exponential Smoothing (ETS)."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    
    train_agg = train_df.groupby("ds")[TARGET].sum()
    test_agg = test_df.groupby("ds")[TARGET].sum()
    
    model = ExponentialSmoothing(
        train_agg,
        trend="add",
        seasonal="add",
        seasonal_periods=7
    )
    fitted = model.fit()
    
    y_pred = fitted.forecast(steps=len(test_agg))
    y_true = test_agg.values
    
    metrics = calc_metrics(pd.Series(y_true), pd.Series(y_pred.values))
    
    joblib.dump(fitted, MODELS_DIR / "ets_demand.joblib")
    return metrics, fitted


def main():
    print("Phase 2.3: Multi-Model Demand Forecasting Comparison")
    print("=" * 55)
    
    # MLflow setup (Windows needs file:/// with forward slashes)
    mlruns_path = PROJECT_ROOT / "mlruns"
    mlruns_path.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(mlruns_path.as_uri())  # Converts to file:///C:/...
    mlflow.set_experiment("demand_forecast_comparison")
    
    print("\nLoading data...")
    df = load_data()
    print(f"  Total rows: {len(df):,}")
    print(f"  Date range: {df['ds'].min().date()} to {df['ds'].max().date()}")
    
    ml_features = get_ml_features(df)
    print(f"  ML Features available: {ml_features}")
    
    # Segment SKUs and Stores
    print("\n--- Segmentation Analysis ---")
    sku_segments = segment_skus(df)
    store_segments = segment_stores(df)
    
    n_skus = len(sku_segments)
    n_forecastable_skus = sku_segments["forecastable"].sum()
    print(f"  SKUs: {n_forecastable_skus}/{n_skus} forecastable ({n_forecastable_skus/n_skus*100:.0f}%)")
    print(f"    ABC: A={len(sku_segments[sku_segments['abc_class']=='A'])}, "
          f"B={len(sku_segments[sku_segments['abc_class']=='B'])}, "
          f"C={len(sku_segments[sku_segments['abc_class']=='C'])}")
    
    n_stores = len(store_segments)
    n_forecastable_stores = store_segments["forecastable"].sum()
    print(f"  Stores: {n_forecastable_stores}/{n_stores} forecastable ({n_forecastable_stores/n_stores*100:.0f}%)")
    
    # Save segmentation
    sku_segments.to_csv(MODELS_DIR / "sku_segmentation.csv", index=False)
    store_segments.to_csv(MODELS_DIR / "store_segmentation.csv", index=False)
    
    # Time-based split (80/20)
    split_date = df["ds"].quantile(0.8)
    train_df = df[df["ds"] < split_date].copy()
    test_df = df[df["ds"] >= split_date].copy()
    print(f"  Train: {len(train_df):,}, Test: {len(test_df):,}")
    
    # --- ML Models (granular predictions) ---
    models_ml = [
        ("XGBoost", train_xgboost),
        ("LightGBM", train_lightgbm),
    ]
    
    # --- Time Series Models (aggregated predictions) ---
    models_ts = [
        ("Prophet", train_prophet),
        ("SARIMA", train_sarima),
        ("ETS", train_ets),
    ]
    
    print("\n--- ML Models (SKU-level) ---")
    granular_results = {}  # Store granular breakdowns per model
    results_agg_all = []   # All items
    results_agg_forecastable = []  # Forecastable only
    
    for name, train_fn in models_ml:
        print(f"\nTraining {name}...")
        try:
            with mlflow.start_run(run_name=name):
                agg_metrics, granular, model = train_fn(train_df, test_df, sku_segments, store_segments)
                mlflow.log_params({"model": name, "type": "ML"})
                
                # Log both all and forecastable metrics
                for prefix, metrics in [("all", agg_metrics["all"]), ("forecastable", agg_metrics["forecastable"])]:
                    mlflow.log_metrics({f"{prefix}_{k}": v for k, v in metrics.items() if not np.isnan(v)})
                
                # Summary stats - overall and forecastable only
                sku_df = granular["by_sku"]
                store_df = granular["by_store"]
                
                # Forecastable items only
                if "forecastable" in sku_df.columns:
                    sku_forecastable = sku_df[sku_df["forecastable"] == True]
                    store_forecastable = store_df[store_df["forecastable"] == True]
                else:
                    sku_forecastable = sku_df
                    store_forecastable = store_df
                
                results_agg_all.append({"Model": name, "Type": "ML", **agg_metrics["all"]})
                results_agg_forecastable.append({"Model": name, "Type": "ML", **agg_metrics["forecastable"]})
                granular_results[name] = granular
                
                print(f"  ALL items:")
                print(f"    WAPE: {agg_metrics['all']['wape']:.1f}%, Bias: {agg_metrics['all']['bias']:+.1f}%, Hit@20%: {agg_metrics['all']['hit_rate_20']:.0f}%")
                print(f"  FORECASTABLE items only:")
                print(f"    WAPE: {agg_metrics['forecastable']['wape']:.1f}%, Bias: {agg_metrics['forecastable']['bias']:+.1f}%, Hit@20%: {agg_metrics['forecastable']['hit_rate_20']:.0f}%")
                print(f"  By SKU (forecastable): Median WAPE: {sku_forecastable['wape'].median():.1f}% ({len(sku_forecastable)} SKUs)")
                print(f"  By Store (forecastable): Median WAPE: {store_forecastable['wape'].median():.1f}% ({len(store_forecastable)} stores)")
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n--- Time Series Models (Aggregated Daily) ---")
    for name, train_fn in models_ts:
        print(f"\nTraining {name}...")
        try:
            with mlflow.start_run(run_name=name):
                metrics, model = train_fn(train_df, test_df)
                mlflow.log_params({"model": name, "type": "TimeSeries"})
                mlflow.log_metrics({k: v for k, v in metrics.items() if not np.isnan(v)})
                # TS models only have "all" (they don't know about SKU segmentation)
                results_agg_all.append({"Model": name, "Type": "TimeSeries", **metrics})
                results_agg_forecastable.append({"Model": name, "Type": "TimeSeries", **metrics})  # Same for TS
                print(f"  WAPE: {metrics['wape']:.1f}%, Bias: {metrics['bias']:+.1f}%, Hit@20%: {metrics['hit_rate_20']:.0f}%, MASE: {metrics['mase']:.2f}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # ==================== STAKEHOLDER SUMMARY ====================
    print("\n" + "=" * 85)
    print("📊 EXECUTIVE SUMMARY - MODEL COMPARISON")
    print("=" * 85)
    
    # Table 1: ALL items (what stakeholders need for budgeting)
    print("\n┌─────────────────────────────────────────────────────────────────────────────────┐")
    print("│ TABLE 1: ALL ITEMS (Use this for budgeting & capacity planning)                 │")
    print("└─────────────────────────────────────────────────────────────────────────────────┘")
    
    results_all_df = pd.DataFrame(results_agg_all).sort_values("wape")
    display_cols = ["Model", "Type", "wape", "bias", "hit_rate_20", "mase", "mae"]
    print(results_all_df[display_cols].to_string(index=False))
    
    # Table 2: FORECASTABLE items only (where ML shines)
    print("\n┌─────────────────────────────────────────────────────────────────────────────────┐")
    print("│ TABLE 2: FORECASTABLE ITEMS ONLY (ML-suitable high-volume, stable demand SKUs)  │")
    print("└─────────────────────────────────────────────────────────────────────────────────┘")
    
    results_forecastable_df = pd.DataFrame(results_agg_forecastable).sort_values("wape")
    print(results_forecastable_df[display_cols].to_string(index=False))
    
    # Coverage stats
    forecastable_volume = df[df["sku"].isin(sku_segments[sku_segments["forecastable"]]["sku"])][TARGET].sum()
    total_volume = df[TARGET].sum()
    coverage_pct = forecastable_volume / total_volume * 100
    
    print(f"\n📈 Coverage: Forecastable SKUs represent {coverage_pct:.1f}% of total demand volume")
    
    # Interpretation guide
    print("\n📋 Metric Guide:")
    print("  WAPE  : % of total demand missed (lower = better, <20% is good)")
    print("  Bias  : +over/-under forecasting (+5% = we predict 5% more than actual)")
    print("  Hit@20: % of predictions within ±20% of actual (higher = better)")
    print("  MASE  : vs naive 'use yesterday' forecast (<1 = better than naive)")
    
    # Save both comparison tables
    results_all_df.to_csv(MODELS_DIR / "model_comparison_all_items.csv", index=False)
    results_forecastable_df.to_csv(MODELS_DIR / "model_comparison_forecastable.csv", index=False)
    
    # Save granular breakdowns for ML models
    print("\n" + "=" * 80)
    print("GRANULAR BREAKDOWNS BY SEGMENT (ML Models)")
    print("=" * 80)
    
    for model_name, granular in granular_results.items():
        sku_df = granular["by_sku"]
        store_df = granular["by_store"]
        
        # Save full results
        sku_path = MODELS_DIR / f"{model_name.lower()}_metrics_by_sku.csv"
        sku_df.to_csv(sku_path, index=False)
        
        store_path = MODELS_DIR / f"{model_name.lower()}_metrics_by_store.csv"
        store_df.to_csv(store_path, index=False)
        
        print(f"\n{model_name}:")
        print(f"  Saved: {sku_path.name}, {store_path.name}")
        
        # Show metrics by segment
        if "forecastable" in sku_df.columns:
            print(f"\n  SKU Metrics by Segment:")
            for fg, label in [(True, "Forecastable"), (False, "Non-forecastable")]:
                subset = sku_df[sku_df["forecastable"] == fg]
                if len(subset) > 0:
                    print(f"    {label}: n={len(subset)}, Median WAPE={subset['wape'].median():.1f}%, "
                          f"Median Bias={subset['bias'].median():+.1f}%")
            
            # ABC class breakdown
            if "abc_class" in sku_df.columns:
                print(f"\n  SKU Metrics by ABC Class:")
                for abc in ["A", "B", "C"]:
                    subset = sku_df[sku_df["abc_class"] == abc]
                    if len(subset) > 0:
                        print(f"    Class {abc}: n={len(subset)}, Median WAPE={subset['wape'].median():.1f}%, "
                              f"Volume={subset['total_actual'].sum():,.0f}")
        
        if "forecastable" in store_df.columns:
            print(f"\n  Store Metrics by Segment:")
            for fg, label in [(True, "Forecastable"), (False, "Non-forecastable")]:
                subset = store_df[store_df["forecastable"] == fg]
                if len(subset) > 0:
                    print(f"    {label}: n={len(subset)}, Median WAPE={subset['wape'].median():.1f}%, "
                          f"Median Bias={subset['bias'].median():+.1f}%")
        
        # Show highest impact items (forecastable only, high volume)
        if "forecastable" in sku_df.columns:
            forecastable_skus = sku_df[sku_df["forecastable"] == True].copy()
        else:
            forecastable_skus = sku_df.copy()
        
        if len(forecastable_skus) > 0:
            forecastable_skus["impact"] = forecastable_skus["wape"] * forecastable_skus["total_actual"]
            worst_skus = forecastable_skus.nlargest(5, "impact")[["sku", "wape", "bias", "total_actual"]]
            print(f"\n  Highest Impact Forecastable SKUs:")
            print(worst_skus.to_string(index=False))
    
    print(f"\n" + "=" * 80)
    print("SEGMENTATION FILES SAVED")
    print("=" * 80)
    print(f"  {MODELS_DIR / 'sku_segmentation.csv'}")
    print(f"  {MODELS_DIR / 'store_segmentation.csv'}")
    
    print(f"\n📋 Segmentation Criteria:")
    print("  Forecastable = Volume >= threshold AND CV <= 1.5 AND NonZero% >= 30%")
    print("  ABC Class = Based on cumulative volume (A=70%, B=90%, C=100%)")
    print("  CV (Coefficient of Variation) = std/mean (lower = more stable demand)")
    
    print(f"\nView MLflow UI: cd {PROJECT_ROOT} && mlflow ui")
    
    best_all = results_all_df.iloc[0]
    best_forecastable = results_forecastable_df.iloc[0]
    print(f"\n🏆 Best Model (All Items): {best_all['Model']} (WAPE: {best_all['wape']:.1f}%, Bias: {best_all['bias']:+.1f}%)")
    print(f"🏆 Best Model (Forecastable): {best_forecastable['Model']} (WAPE: {best_forecastable['wape']:.1f}%, Bias: {best_forecastable['bias']:+.1f}%)")


if __name__ == "__main__":
    main()
