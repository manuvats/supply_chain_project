"""
Anomaly Detection - Pandas Version
Detects: demand spikes/drops, stockouts, revenue anomalies
Methods: Z-score, IQR, Isolation Forest
"""
import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
from sklearn.ensemble import IsolationForest

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
OUTPUT_TABLE = "main_features.anomalies"


def load_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load demand features from DuckDB."""
    return con.execute("""
        SELECT * FROM main_features.demand_features
    """).df()


def detect_zscore_anomalies(df: pd.DataFrame, col: str, threshold: float = 3.0) -> pd.Series:
    """Flag anomalies using Z-score method."""
    mean = df[col].mean()
    std = df[col].std()
    z_scores = (df[col] - mean) / std
    return (z_scores.abs() > threshold).astype(int)


def detect_iqr_anomalies(df: pd.DataFrame, col: str, multiplier: float = 1.5) -> pd.Series:
    """Flag anomalies using IQR method."""
    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return ((df[col] < lower) | (df[col] > upper)).astype(int)


def detect_isolation_forest_anomalies(df: pd.DataFrame, cols: list, contamination: float = 0.05) -> pd.Series:
    """Flag anomalies using Isolation Forest."""
    X = df[cols].fillna(0)
    iso = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
    preds = iso.fit_predict(X)
    # -1 = anomaly, 1 = normal → convert to 0/1
    return (preds == -1).astype(int)


def detect_demand_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect demand-related anomalies."""
    # Demand spike/drop using Z-score
    df["anomaly_demand_zscore"] = detect_zscore_anomalies(df, "units_sold")
    
    # Demand anomaly using IQR
    df["anomaly_demand_iqr"] = detect_iqr_anomalies(df, "units_sold")
    
    # Demand vs rolling mean (contextual anomaly)
    df["demand_deviation"] = (df["units_sold"] - df["units_sold_roll_mean_7"]) / df["units_sold_roll_std_7"].replace(0, 1)
    df["anomaly_demand_contextual"] = (df["demand_deviation"].abs() > 2.5).astype(int)
    
    return df


def detect_stockout_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect supply-demand mismatch anomalies."""
    # Stockout flag already exists
    df["anomaly_stockout"] = df["stockout_flag"].astype(int)
    
    # Lost sales ratio
    df["lost_sales_ratio"] = df["demand"] / df["units_sold"].replace(0, 1) - 1
    df["anomaly_high_lost_sales"] = (df["lost_sales_ratio"] > 0.2).astype(int)
    
    return df


def detect_revenue_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect revenue anomalies."""
    df["anomaly_revenue_zscore"] = detect_zscore_anomalies(df, "revenue")
    df["anomaly_revenue_iqr"] = detect_iqr_anomalies(df, "revenue")
    return df


def detect_multivariate_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Detect multivariate anomalies using Isolation Forest."""
    feature_cols = [
        "units_sold", "revenue", "demand",
        "units_sold_roll_mean_7", "units_sold_roll_std_7"
    ]
    df["anomaly_isolation_forest"] = detect_isolation_forest_anomalies(df, feature_cols)
    return df


def create_anomaly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create combined anomaly score."""
    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    df["anomaly_score"] = df[anomaly_cols].sum(axis=1)
    df["is_anomaly"] = (df["anomaly_score"] >= 2).astype(int)  # At least 2 flags
    return df


def main():
    con = duckdb.connect(str(DB_PATH))
    
    print("Loading features...")
    df = load_features(con)
    print(f"Loaded {len(df):,} rows")
    
    print("Detecting demand anomalies...")
    df = detect_demand_anomalies(df)
    
    print("Detecting stockout anomalies...")
    df = detect_stockout_anomalies(df)
    
    print("Detecting revenue anomalies...")
    df = detect_revenue_anomalies(df)
    
    print("Detecting multivariate anomalies...")
    df = detect_multivariate_anomalies(df)
    
    print("Creating anomaly summary...")
    df = create_anomaly_summary(df)
    
    # Stats
    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    print("\nAnomaly counts:")
    for col in anomaly_cols:
        count = df[col].sum()
        pct = count / len(df) * 100
        print(f"  {col}: {count:,} ({pct:.2f}%)")
    
    print(f"\nTotal flagged anomalies (score >= 2): {df['is_anomaly'].sum():,}")
    
    print(f"\nWriting to {OUTPUT_TABLE}...")
    con.execute(f"DROP TABLE IF EXISTS {OUTPUT_TABLE}")
    con.execute(f"CREATE TABLE {OUTPUT_TABLE} AS SELECT * FROM df")
    
    con.close()
    print("Done!")


if __name__ == "__main__":
    main()