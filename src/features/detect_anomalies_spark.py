"""
Anomaly Detection - PySpark Version
Detects: demand spikes/drops, stockouts, revenue anomalies
Methods: Z-score, IQR, Isolation Forest (via pandas UDF)
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
FEATURES_PATH = PROJECT_ROOT / "data" / "features_spark" / "demand_features"
OUTPUT_PATH = PROJECT_ROOT / "data" / "features_spark" / "anomalies"


def get_spark() -> SparkSession:
    """Initialize Spark."""
    return (
        SparkSession.builder
        .appName("AnomalyDetection")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )


def load_features(spark: SparkSession):
    """Load features via Pandas."""
    print("  Reading features via Pandas...")
    pdf = pd.read_parquet(str(FEATURES_PATH))
    print(f"  Loaded {len(pdf):,} rows")
    return spark.createDataFrame(pdf)


def add_zscore_anomaly(df, col: str, threshold: float = 3.0, output_col: str = None):
    """Add Z-score based anomaly flag."""
    output_col = output_col or f"anomaly_{col}_zscore"
    
    # Calculate mean and std
    stats = df.agg(F.mean(col).alias("mean"), F.stddev(col).alias("std")).collect()[0]
    mean_val, std_val = stats["mean"], stats["std"]
    
    # Z-score and flag
    df = df.withColumn(
        output_col,
        F.when(F.abs((F.col(col) - mean_val) / std_val) > threshold, 1).otherwise(0)
    )
    return df


def add_iqr_anomaly(df, col: str, multiplier: float = 1.5, output_col: str = None):
    """Add IQR based anomaly flag."""
    output_col = output_col or f"anomaly_{col}_iqr"
    
    # Calculate quartiles
    quantiles = df.approxQuantile(col, [0.25, 0.75], 0.01)
    q1, q3 = quantiles[0], quantiles[1]
    iqr = q3 - q1
    lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
    
    df = df.withColumn(
        output_col,
        F.when((F.col(col) < lower) | (F.col(col) > upper), 1).otherwise(0)
    )
    return df


def detect_demand_anomalies(df):
    """Detect demand anomalies."""
    # Z-score
    df = add_zscore_anomaly(df, "units_sold", output_col="anomaly_demand_zscore")
    
    # IQR
    df = add_iqr_anomaly(df, "units_sold", output_col="anomaly_demand_iqr")
    
    # Contextual: deviation from rolling mean
    df = df.withColumn(
        "demand_deviation",
        (F.col("units_sold") - F.col("units_sold_roll_mean_7")) / 
        F.when(F.col("units_sold_roll_std_7") == 0, 1).otherwise(F.col("units_sold_roll_std_7"))
    )
    df = df.withColumn(
        "anomaly_demand_contextual",
        F.when(F.abs(F.col("demand_deviation")) > 2.5, 1).otherwise(0)
    )
    
    return df


def detect_stockout_anomalies(df):
    """Detect stockout anomalies."""
    df = df.withColumn("anomaly_stockout", F.col("stockout_flag").cast(IntegerType()))
    
    # Lost sales ratio
    df = df.withColumn(
        "lost_sales_ratio",
        F.col("demand") / F.when(F.col("units_sold") == 0, 1).otherwise(F.col("units_sold")) - 1
    )
    df = df.withColumn(
        "anomaly_high_lost_sales",
        F.when(F.col("lost_sales_ratio") > 0.2, 1).otherwise(0)
    )
    
    return df


def detect_revenue_anomalies(df):
    """Detect revenue anomalies."""
    df = add_zscore_anomaly(df, "revenue", output_col="anomaly_revenue_zscore")
    df = add_iqr_anomaly(df, "revenue", output_col="anomaly_revenue_iqr")
    return df


def detect_isolation_forest_anomalies(df, feature_cols: list, contamination: float = 0.05):
    """Run Isolation Forest via Pandas (collect to driver)."""
    from sklearn.ensemble import IsolationForest
    
    print("  Running Isolation Forest (via Pandas)...")
    pdf = df.select("ds", "sku", "store_id", *feature_cols).toPandas()
    
    X = pdf[feature_cols].fillna(0)
    iso = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
    pdf["anomaly_isolation_forest"] = (iso.fit_predict(X) == -1).astype(int)
    
    # Join back
    iso_df = df.sparkSession.createDataFrame(pdf[["ds", "sku", "store_id", "anomaly_isolation_forest"]])
    df = df.join(iso_df, on=["ds", "sku", "store_id"], how="left")
    
    return df


def create_anomaly_summary(df):
    """Create combined anomaly score."""
    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    
    # Sum all anomaly flags
    df = df.withColumn(
        "anomaly_score",
        sum(F.col(c) for c in anomaly_cols)
    )
    df = df.withColumn(
        "is_anomaly",
        F.when(F.col("anomaly_score") >= 2, 1).otherwise(0)
    )
    
    return df


def main():
    print("Initializing Spark...")
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    
    print("Loading features...")
    df = load_features(spark)
    df.cache()
    
    print("Detecting demand anomalies...")
    df = detect_demand_anomalies(df)
    
    print("Detecting stockout anomalies...")
    df = detect_stockout_anomalies(df)
    
    print("Detecting revenue anomalies...")
    df = detect_revenue_anomalies(df)
    
    print("Detecting multivariate anomalies...")
    feature_cols = ["units_sold", "revenue", "demand", "units_sold_roll_mean_7", "units_sold_roll_std_7"]
    df = detect_isolation_forest_anomalies(df, feature_cols)
    
    print("Creating anomaly summary...")
    df = create_anomaly_summary(df)
    
    # Stats
    print("\nAnomaly counts:")
    anomaly_cols = [c for c in df.columns if c.startswith("anomaly_")]
    for col in anomaly_cols:
        count = df.filter(F.col(col) == 1).count()
        total = df.count()
        pct = count / total * 100
        print(f"  {col}: {count:,} ({pct:.2f}%)")
    
    total_anomalies = df.filter(F.col("is_anomaly") == 1).count()
    print(f"\nTotal flagged anomalies (score >= 2): {total_anomalies:,}")
    
    print(f"\nWriting to {OUTPUT_PATH}...")
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    df.toPandas().to_parquet(OUTPUT_PATH / "anomalies.parquet", index=False)
    
    spark.stop()
    print("Done!")


if __name__ == "__main__":
    main()
