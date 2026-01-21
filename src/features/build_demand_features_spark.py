"""
Demand Feature Engineering - PySpark Version
Reads from Bronze (Parquet) → Writes feature table to Parquet

Note: Uses Pandas for I/O to avoid Hadoop native library issues on Windows.
      All transformations are done in Spark to demonstrate PySpark skills.
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pathlib import Path

# Config
PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "sales"
OUTPUT_PATH = PROJECT_ROOT / "data" / "features_spark" / "demand_features"


def get_spark() -> SparkSession:
    """Initialize Spark (local mode, no Hadoop dependency)."""
    return (
        SparkSession.builder
        .appName("DemandFeatures")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")  # Faster Pandas conversion
        .getOrCreate()
    )


def load_sales_data(spark: SparkSession):
    """Load sales from Bronze - using Pandas to avoid Hadoop native IO issues."""
    import pandas as pd
    
    print("  Reading parquet via Pandas...")
    pdf = pd.read_parquet(str(BRONZE_PATH))
    print(f"  Loaded {len(pdf):,} rows into Pandas")
    
    print("  Converting to Spark DataFrame (this may take a minute)...")
    df = spark.createDataFrame(pdf)
    
    print("  Selecting columns...")
    return (
        df.select(
            F.col("date").alias("ds"),
            "sku",
            "store_id",
            "units_sold",
            "demand",
            "revenue",
            "is_promo",
            "stockout_flag",
            F.dayofweek("date").alias("day_of_week"),
            F.month("date").alias("month"),
            F.year("date").alias("year")
        )
    )


def add_lag_features(df, group_cols: list, target: str, lags: list):
    """Add lagged values using window functions."""
    window = Window.partitionBy(group_cols).orderBy("ds")
    
    for lag in lags:
        df = df.withColumn(f"{target}_lag_{lag}", F.lag(target, lag).over(window))
    
    return df


def add_rolling_features(df, group_cols: list, target: str, windows: list):
    """Add rolling statistics using window functions."""
    for window_size in windows:
        # Window: rows between (window_size+1) days ago and 1 day ago (exclude current)
        w = (
            Window.partitionBy(group_cols)
            .orderBy("ds")
            .rowsBetween(-window_size, -1)
        )
        
        df = (
            df
            .withColumn(f"{target}_roll_mean_{window_size}", F.avg(target).over(w))
            .withColumn(f"{target}_roll_std_{window_size}", F.stddev(target).over(w))
            .withColumn(f"{target}_roll_min_{window_size}", F.min(target).over(w))
            .withColumn(f"{target}_roll_max_{window_size}", F.max(target).over(w))
        )
    
    return df


def add_date_features(df):
    """Add calendar features."""
    return (
        df
        .withColumn("is_weekend", F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0))
        .withColumn("quarter", F.quarter("ds"))
    )


def add_aggregation_features(df):
    """Add SKU and store level aggregations."""
    # SKU-level totals per day
    sku_agg = (
        df.groupBy("sku", "ds")
        .agg(F.sum("units_sold").alias("sku_total_qty"))
    )
    
    # Store-level totals per day
    store_agg = (
        df.groupBy("store_id", "ds")
        .agg(F.sum("units_sold").alias("store_total_qty"))
    )
    
    df = df.join(sku_agg, on=["sku", "ds"], how="left")
    df = df.join(store_agg, on=["store_id", "ds"], how="left")
    
    return df


def build_features(df):
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
    print("Initializing Spark...")
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    
    print("Loading sales data from Bronze...")
    df = load_sales_data(spark)
    
    # Cache to avoid recomputing
    print("Caching data...")
    df.cache()
    initial_count = df.count()
    print(f"Loaded {initial_count:,} rows")
    
    print("Building features...")
    df = build_features(df)
    
    # Drop rows with insufficient history
    print("Filtering rows with insufficient history...")
    df = df.filter(F.col("units_sold_lag_7").isNotNull())
    df.cache()
    final_count = df.count()
    print(f"Dropped {initial_count - final_count:,} rows with insufficient history")
    
    print(f"Writing {final_count:,} rows to {OUTPUT_PATH}...")
    
    # Convert to Pandas and write (avoids Hadoop native IO)
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    df.toPandas().to_parquet(OUTPUT_PATH / "features.parquet", index=False)
    
    # Show sample
    print("\nFeature sample:")
    df.show(5, truncate=False)
    
    # Show schema
    print("\nFeature schema:")
    df.printSchema()
    
    spark.stop()
    print("\nDone!")


if __name__ == "__main__":
    main()