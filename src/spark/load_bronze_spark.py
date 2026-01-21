"""
Bronze Layer Ingestion - PySpark Version
Reads raw parquet from Google Drive → Writes Delta Lake locally.

Parallel implementation to load_bronze.py (Pandas version)
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, current_timestamp, lit
from pyspark.sql.types import TimestampType
from datetime import datetime
import os

# === CONFIGURATION ===
RAW_DATA_PATH = "H:/My Drive/supply_chain_raw"
BRONZE_PATH = "C:/Users/Manu/supply_chain_project/data/bronze_spark"

DATE_COLUMNS = {
    "sales": ["date"],
    "demand_forecasts": ["forecast_date"],
    "inventory": ["snapshot_date"],
    "purchase_orders": ["order_date", "expected_date", "actual_date"],
    "shipments": ["planned_ship_date", "actual_ship_date", "planned_delivery_date", "actual_delivery_date"],
    "production_orders": ["planned_date", "completion_date"],
}


def create_spark_session():
    """Create SparkSession with Delta Lake support"""
    spark = SparkSession.builder \
        .appName("SupplyChain-Bronze") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "8") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_parquet(spark: SparkSession, name: str, path: str):
    """Load parquet file and parse date columns"""
    print(f"  Loading {name}...")
    
    df = spark.read.parquet(path)
    
    # Parse date columns
    if name in DATE_COLUMNS:
        for date_col in DATE_COLUMNS[name]:
            if date_col in df.columns:
                df = df.withColumn(date_col, to_timestamp(col(date_col)))
    
    # Add metadata columns
    df = df.withColumn("_loaded_at", current_timestamp())
    df = df.withColumn("_source_file", lit(path))
    
    row_count = df.count()
    print(f"    → {row_count:,} rows")
    
    return df


def write_to_delta(df, name: str, bronze_path: str):
    """Write DataFrame to Delta Lake"""
    output_path = f"{bronze_path}/{name}"
    
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(output_path)
    
    print(f"  ✓ {name} → Delta Lake")


def load_bronze_layer():
    """Main ingestion function"""
    print("=" * 60)
    print("BRONZE LAYER INGESTION (PySpark)")
    print("=" * 60)
    print(f"Source: {RAW_DATA_PATH} (Google Drive)")
    print(f"Target: {BRONZE_PATH} (Local Delta Lake)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create output directory
    os.makedirs(BRONZE_PATH, exist_ok=True)
    
    # Create Spark session
    print("Initializing Spark...")
    spark = create_spark_session()
    print(f"Spark version: {spark.version}")
    print()
    
    # Tables to load
    tables = [
        "suppliers", "products", "locations", "carriers", "supplier_product_map",
        "purchase_orders", "shipments", "production_orders",
        "sales", "demand_forecasts", "inventory"
    ]
    
    print("[1/1] Loading all tables...")
    for name in tables:
        source_file = f"{RAW_DATA_PATH}/{name}.parquet"
        if os.path.exists(source_file):
            df = load_parquet(spark, name, source_file)
            write_to_delta(df, name, BRONZE_PATH)
        else:
            print(f"  ⚠ {name}.parquet not found, skipping...")
    
    print("\n" + "=" * 60)
    print("✅ BRONZE LAYER COMPLETE (PySpark)")
    print("=" * 60)
    
    spark.stop()


def verify_bronze_layer():
    """Verify Bronze layer"""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    spark = create_spark_session()
    
    for table_name in os.listdir(BRONZE_PATH):
        table_path = f"{BRONZE_PATH}/{table_name}"
        if os.path.isdir(table_path) and not table_name.startswith('.'):
            try:
                df = spark.read.format("delta").load(table_path)
                count = df.count()
                print(f"  ✓ {table_name}: {count:,} rows")
            except Exception as e:
                print(f"  ✗ {table_name}: Error - {e}")
    
    spark.stop()


if __name__ == "__main__":
    load_bronze_layer()
    verify_bronze_layer()
