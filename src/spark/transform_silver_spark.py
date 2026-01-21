"""
Silver Layer Transformations - PySpark Version
Cleans and stages Bronze data into Silver layer.

Parallel implementation to dbt Silver models.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, when, coalesce, current_timestamp,
    year, month, dayofweek, dayofyear, quarter,
    date_trunc, round as spark_round
)
from datetime import datetime
import os

# === CONFIGURATION ===
BRONZE_PATH = "C:/Users/Manu/supply_chain_project/data/bronze_spark"
SILVER_PATH = "C:/Users/Manu/supply_chain_project/data/silver_spark"


def create_spark_session():
    """Create SparkSession with Delta Lake support"""
    spark = SparkSession.builder \
        .appName("SupplyChain-Silver") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_bronze(spark: SparkSession, table_name: str):
    """Read from Bronze Delta Lake"""
    return spark.read.format("delta").load(f"{BRONZE_PATH}/{table_name}")


def write_silver(df, table_name: str):
    """Write to Silver Delta Lake"""
    output_path = f"{SILVER_PATH}/{table_name}"
    
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(output_path)
    
    print(f"  ✓ {table_name}: {df.count():,} rows")


def transform_stg_products(spark: SparkSession):
    """
    Transform products - equivalent to stg_products.sql
    Adds: unit_margin, margin_pct
    """
    df = read_bronze(spark, "products")
    
    result = df.select(
        col("sku"),
        col("product_name"),
        col("category"),
        col("unit_cost"),
        col("unit_price"),
        (col("unit_price") - col("unit_cost")).alias("unit_margin"),
        spark_round(
            (col("unit_price") - col("unit_cost")) / col("unit_price") * 100, 2
        ).alias("margin_pct"),
        col("unit_weight_kg"),
        col("shelf_life_days"),
        col("is_hazardous"),
        col("abc_class"),
        col("safety_stock_days"),
        current_timestamp().alias("_loaded_at")
    )
    
    return result


def transform_stg_suppliers(spark: SparkSession):
    """
    Transform suppliers - equivalent to stg_suppliers.sql
    Adds: reliability_tier
    """
    df = read_bronze(spark, "suppliers")
    
    result = df.select(
        col("supplier_id"),
        col("supplier_name"),
        col("region"),
        col("lead_time_days"),
        col("lead_time_std"),
        col("reliability_score"),
        col("unit_cost_multiplier"),
        col("min_order_qty"),
        col("payment_terms_days"),
        when(col("reliability_score") >= 0.95, "Excellent")
            .when(col("reliability_score") >= 0.85, "Good")
            .when(col("reliability_score") >= 0.70, "Fair")
            .otherwise("Poor").alias("reliability_tier"),
        current_timestamp().alias("_loaded_at")
    )
    
    return result


def transform_stg_sales(spark: SparkSession):
    """
    Transform sales - equivalent to stg_sales.sql
    Adds: lost_sales, date dimensions, fiscal calendar
    """
    df = read_bronze(spark, "sales")
    
    # Filter nulls
    df = df.filter(col("units_sold").isNotNull())
    
    result = df.select(
        col("date"),
        col("store_id"),
        col("sku"),
        col("units_sold"),
        col("demand"),
        (col("demand") - col("units_sold")).alias("lost_sales"),
        col("revenue"),
        col("is_promo"),
        col("stockout_flag"),
        
        # Date dimensions
        date_trunc("week", col("date")).alias("week_start"),
        date_trunc("month", col("date")).alias("month_start"),
        date_trunc("quarter", col("date")).alias("quarter_start"),
        year(col("date")).alias("year"),
        month(col("date")).alias("month"),
        dayofweek(col("date")).alias("day_of_week"),
        dayofyear(col("date")).alias("day_of_year"),
        
        # Fiscal calendar (April start)
        when(month(col("date")) >= 4, year(col("date")))
            .otherwise(year(col("date")) - 1).alias("fiscal_year"),
        when(month(col("date")) >= 4, month(col("date")) - 3)
            .otherwise(month(col("date")) + 9).alias("fiscal_month"),
        
        current_timestamp().alias("_loaded_at")
    )
    
    return result


def transform_stg_inventory(spark: SparkSession):
    """
    Transform inventory - equivalent to stg_inventory.sql
    Adds: total_available_qty, net_position, health flags
    """
    df = read_bronze(spark, "inventory")
    
    # Filter nulls
    df = df.filter(col("on_hand_qty").isNotNull())
    
    result = df.select(
        col("snapshot_date"),
        col("location_id"),
        col("sku"),
        col("on_hand_qty"),
        col("in_transit_qty"),
        col("backorder_qty"),
        col("inventory_value"),
        
        # Derived fields
        (coalesce(col("on_hand_qty"), lit(0)) + 
         coalesce(col("in_transit_qty"), lit(0))).alias("total_available_qty"),
        (coalesce(col("on_hand_qty"), lit(0)) + 
         coalesce(col("in_transit_qty"), lit(0)) - 
         coalesce(col("backorder_qty"), lit(0))).alias("net_position"),
        
        # Health flags
        when(col("on_hand_qty") == 0, True).otherwise(False).alias("is_stockout"),
        when(col("on_hand_qty") < 50, True).otherwise(False).alias("is_low_stock"),
        
        # Date dimensions
        date_trunc("month", col("snapshot_date")).alias("month_start"),
        year(col("snapshot_date")).alias("year"),
        month(col("snapshot_date")).alias("month"),
        
        current_timestamp().alias("_loaded_at")
    )
    
    return result


def run_silver_transformations():
    """Run all Silver transformations"""
    print("=" * 60)
    print("SILVER LAYER TRANSFORMATIONS (PySpark)")
    print("=" * 60)
    print(f"Source: {BRONZE_PATH}")
    print(f"Target: {SILVER_PATH}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    os.makedirs(SILVER_PATH, exist_ok=True)
    
    spark = create_spark_session()
    print(f"Spark version: {spark.version}\n")
    
    print("Running transformations...")
    
    # Products
    stg_products = transform_stg_products(spark)
    write_silver(stg_products, "stg_products")
    
    # Suppliers
    stg_suppliers = transform_stg_suppliers(spark)
    write_silver(stg_suppliers, "stg_suppliers")
    
    # Sales
    stg_sales = transform_stg_sales(spark)
    write_silver(stg_sales, "stg_sales")
    
    # Inventory
    stg_inventory = transform_stg_inventory(spark)
    write_silver(stg_inventory, "stg_inventory")
    
    print("\n" + "=" * 60)
    print("✅ SILVER LAYER COMPLETE (PySpark)")
    print("=" * 60)
    
    spark.stop()


if __name__ == "__main__":
    run_silver_transformations()
