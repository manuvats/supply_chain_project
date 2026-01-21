"""
Demand Feature Engineering - Pandas Version
Reads from Silver layer (DuckDB) → Writes feature table back to DuckDB
"""
import pandas as pd
import duckdb
from pathlib import Path

# Config
PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
OUTPUT_TABLE = "main_features.demand_features"


def load_sales_data(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load cleaned sales from Silver layer."""
    return con.execute("""
        SELECT 
            date as ds,
            sku,
            store_id,
            units_sold,
            revenue,
            DAYOFWEEK(date) as day_of_week,
            MONTH(date) as month,
            YEAR(date) as year
        FROM main_silver.stg_sales
        ORDER BY sku, store_id, date
    """).df()


def add_lag_features(df: pd.DataFrame, group_cols: list, target: str, lags: list) -> pd.DataFrame:
    """Add lagged values for target column."""
    for lag in lags:
        df[f"{target}_lag_{lag}"] = df.groupby(group_cols)[target].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, group_cols: list, target: str, windows: list) -> pd.DataFrame:
    """Add rolling statistics."""
    for window in windows:
        rolled = df.groupby(group_cols)[target].transform(
            lambda x: x.shift(1).rolling(window, min_periods=1)
        )
        df[f"{target}_roll_mean_{window}"] = rolled.mean()
        df[f"{target}_roll_std_{window}"] = rolled.std()
        df[f"{target}_roll_min_{window}"] = rolled.min()
        df[f"{target}_roll_max_{window}"] = rolled.max()
    return df


def add_date_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar features."""
    df["is_weekend"] = df["day_of_week"].isin([6, 7]).astype(int)
    df["is_month_start"] = (pd.to_datetime(df["ds"]).dt.day <= 7).astype(int)
    df["is_month_end"] = (pd.to_datetime(df["ds"]).dt.day >= 24).astype(int)
    df["quarter"] = ((df["month"] - 1) // 3) + 1
    return df


def add_aggregation_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add SKU and store level aggregations."""
    # SKU-level stats (across all stores)
    sku_stats = df.groupby(["sku", "ds"])["units_sold"].sum().reset_index()
    sku_stats.columns = ["sku", "ds", "sku_total_qty"]
    df = df.merge(sku_stats, on=["sku", "ds"], how="left")
    
    # Store-level stats (across all SKUs)
    store_stats = df.groupby(["store_id", "ds"])["units_sold"].sum().reset_index()
    store_stats.columns = ["store_id", "ds", "store_total_qty"]
    df = df.merge(store_stats, on=["store_id", "ds"], how="left")
    
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Main feature engineering pipeline."""
    group_cols = ["sku", "store_id"]
    
    # Lag features
    df = add_lag_features(df, group_cols, "units_sold", lags=[7, 14, 30])
    
    # Rolling features
    df = add_rolling_features(df, group_cols, "units_sold", windows=[7, 14, 30])
    
    # Calendar features
    df = add_date_features(df)
    
    # Aggregations
    df = add_aggregation_features(df)
    
    return df


def main():
    con = duckdb.connect(str(DB_PATH))
    
    # Create features schema if not exists
    con.execute("CREATE SCHEMA IF NOT EXISTS main_features")
    
    print("Loading sales data...")
    df = load_sales_data(con)
    print(f"Loaded {len(df):,} rows")
    
    print("Building features...")
    df = build_features(df)
    
    # Drop rows with NaN from lag features (first N days per group)
    initial_rows = len(df)
    df = df.dropna(subset=["units_sold_lag_7"])
    print(f"Dropped {initial_rows - len(df):,} rows with insufficient history")
    
    print(f"Writing {len(df):,} rows to {OUTPUT_TABLE}...")
    con.execute(f"DROP TABLE IF EXISTS {OUTPUT_TABLE}")
    con.execute(f"CREATE TABLE {OUTPUT_TABLE} AS SELECT * FROM df")
    
    # Show sample
    print("\nFeature sample:")
    print(con.execute(f"SELECT * FROM {OUTPUT_TABLE} LIMIT 5").df().to_string())
    
    # Show feature stats
    print("\nFeature columns:")
    print(con.execute(f"DESCRIBE {OUTPUT_TABLE}").df()[["column_name", "column_type"]].to_string())
    
    con.close()
    print("\nDone!")


if __name__ == "__main__":
    main()