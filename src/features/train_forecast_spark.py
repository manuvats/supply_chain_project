"""
Phase 2.3: Demand Forecasting Model Training - PySpark MLlib
Reads from demand_features → Trains GBTRegressor → Logs to MLflow

Uses hybrid approach (DuckDB→Pandas→Spark) to avoid Windows Hadoop issues.
"""
import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import GBTRegressor
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline
import mlflow
import mlflow.spark
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
TARGET_COL = "units_sold"


def get_spark():
    """Create Spark session (local mode)."""
    return SparkSession.builder \
        .appName("DemandForecast") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .getOrCreate()


def load_features_via_pandas() -> pd.DataFrame:
    """Load from DuckDB via Pandas to avoid Hadoop issues."""
    con = duckdb.connect(str(DB_PATH))
    df = con.execute("SELECT * FROM main_features.demand_features ORDER BY ds").df()
    con.close()
    
    # Drop nulls, convert types
    df = df.dropna(subset=FEATURE_COLS)
    if "is_promo" in df.columns:
        df["is_promo"] = df["is_promo"].astype(int)
    
    # Ensure numeric types for Spark
    for col in FEATURE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce")
    df = df.dropna(subset=FEATURE_COLS + [TARGET_COL])
    
    return df


def train_model(spark, pdf: pd.DataFrame):
    """Train GBTRegressor with time-based train/test split."""
    MODELS_DIR.mkdir(exist_ok=True)
    
    # Convert to Spark DataFrame
    sdf = spark.createDataFrame(pdf)
    
    # Assembler for features
    assembler = VectorAssembler(inputCols=FEATURE_COLS, outputCol="features")
    
    # GBT Regressor (Spark's gradient boosted trees)
    gbt = GBTRegressor(
        featuresCol="features",
        labelCol=TARGET_COL,
        maxIter=100,
        maxDepth=6,
        stepSize=0.1,
        seed=42
    )
    
    pipeline = Pipeline(stages=[assembler, gbt])
    
    # Time-based split (80/20)
    total = sdf.count()
    train_size = int(total * 0.8)
    
    # Add row number for splitting
    sdf = sdf.withColumn("row_id", 
        spark._sc._jvm.org.apache.spark.sql.functions.monotonically_increasing_id())
    train_df = sdf.filter(f"row_id < {train_size}")
    test_df = sdf.filter(f"row_id >= {train_size}")
    
    print(f"  Train: {train_df.count():,}, Test: {test_df.count():,}")
    
    # MLflow setup
    mlflow.set_tracking_uri(f"file://{PROJECT_ROOT / 'mlruns'}")
    mlflow.set_experiment("demand_forecasting_spark")
    
    with mlflow.start_run(run_name=f"spark_gbt_{datetime.now():%Y%m%d_%H%M}"):
        # Log params
        mlflow.log_params({
            "model": "GBTRegressor",
            "maxIter": 100,
            "maxDepth": 6,
            "stepSize": 0.1,
            "train_size": train_df.count(),
            "test_size": test_df.count(),
        })
        
        # Train
        print("\nTraining GBT model...")
        model = pipeline.fit(train_df)
        
        # Predict
        predictions = model.transform(test_df)
        
        # Evaluate
        evaluator_mae = RegressionEvaluator(
            labelCol=TARGET_COL, predictionCol="prediction", metricName="mae")
        evaluator_rmse = RegressionEvaluator(
            labelCol=TARGET_COL, predictionCol="prediction", metricName="rmse")
        
        mae = evaluator_mae.evaluate(predictions)
        rmse = evaluator_rmse.evaluate(predictions)
        
        # MAPE (manual calc)
        pred_pdf = predictions.select(TARGET_COL, "prediction").toPandas()
        mape = np.mean(np.abs((pred_pdf[TARGET_COL] - pred_pdf["prediction"]) 
                              / pred_pdf[TARGET_COL].replace(0, np.nan))) * 100
        
        mlflow.log_metrics({"mae": mae, "rmse": rmse, "mape": mape})
        
        # Log model
        mlflow.spark.log_model(model, "model")
        
        # Save locally
        model_path = str(MODELS_DIR / "demand_forecast_spark")
        model.write().overwrite().save(model_path)
        
        # Feature importance from GBT
        gbt_model = model.stages[-1]
        importance = pd.DataFrame({
            "feature": FEATURE_COLS,
            "importance": gbt_model.featureImportances.toArray()
        }).sort_values("importance", ascending=False)
        
        print(f"\nTest Metrics: MAE={mae:.2f}, RMSE={rmse:.2f}, MAPE={mape:.2f}%")
        print(f"\nTop Features:\n{importance.head(10).to_string(index=False)}")
        print(f"\nModel saved: {model_path}")
        print(f"MLflow run logged to: {PROJECT_ROOT / 'mlruns'}")
        
        return model, importance


def main():
    print("Phase 2.3: Training Demand Forecast Model (Spark MLlib)")
    print("=" * 50)
    
    print("Loading features via DuckDB→Pandas...")
    pdf = load_features_via_pandas()
    print(f"  Rows: {len(pdf):,}")
    
    print("\nInitializing Spark...")
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    
    print("\nTraining GBTRegressor...")
    model, importance = train_model(spark, pdf)
    
    spark.stop()
    print("\nDone!")


if __name__ == "__main__":
    main()
