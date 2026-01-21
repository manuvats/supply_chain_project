"""
Gold Layer Transformations - PySpark Version
Aggregates Silver data into analytics-ready Gold tables.

Parallel implementation to dbt Gold models.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, when, coalesce, current_timestamp, sum as spark_sum,
    count, avg, min as spark_min, max as spark_max, countDistinct,
    round as spark_round
)
from datetime import datetime
import os

# === CONFIGURATION ===
SILVER_PATH = "C:/Users/Manu/supply_chain_project/data/silver_spark"
GOLD_PATH = "C:/Users/Manu/supply_chain_project/data/gold_spark"


def create_spark_session():
    """Create SparkSession with Delta Lake support"""
    spark = SparkSession.builder \
        .appName("SupplyChain-Gold") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_silver(spark: SparkSession, table_name: str):
    """Read from Silver Delta Lake"""
    return spark.read.format("delta").load(f"{SILVER_PATH}/{table_name}")


def write_gold(df, table_name: str):
    """Write to Gold Delta Lake"""
    output_path = f"{GOLD_PATH}/{table_name}"
    
    df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(output_path)
    
    print(f"  ✓ {table_name}: {df.count():,} rows")


def transform_fct_weekly_sales(spark: SparkSession):
    """
    Weekly sales aggregation - equivalent to fct_weekly_sales.sql
    """
    df = read_silver(spark, "stg_sales")
    
    result = df.groupBy("week_start", "store_id", "sku").agg(
        # Volume metrics
        spark_sum("units_sold").alias("total_units"),
        spark_sum("demand").alias("total_demand"),
        spark_sum("lost_sales").alias("total_lost_sales"),
        
        # Financial metrics
        spark_round(spark_sum("revenue"), 2).alias("total_revenue"),
        
        # Promo metrics
        spark_sum(when(col("is_promo"), col("units_sold")).otherwise(0)).alias("promo_units"),
        spark_sum(when(col("is_promo"), col("revenue")).otherwise(0)).alias("promo_revenue"),
        
        # Stockout metrics
        spark_sum(when(col("stockout_flag"), 1).otherwise(0)).alias("stockout_days"),
        
        # Daily averages
        spark_round(avg("units_sold"), 2).alias("avg_daily_units"),
        spark_round(avg("revenue"), 2).alias("avg_daily_revenue"),
        
        count("*").alias("num_days")
    )
    
    # Add derived metrics
    result = result.withColumn(
        "lost_sales_pct",
        spark_round(col("total_lost_sales") / col("total_demand") * 100, 2)
    ).withColumn(
        "fill_rate",
        spark_round(col("total_units") / col("total_demand") * 100, 2)
    )
    
    return result


def transform_fct_monthly_sales(spark: SparkSession):
    """
    Monthly sales aggregation - equivalent to fct_monthly_sales.sql
    """
    df = read_silver(spark, "stg_sales")
    
    result = df.groupBy("month_start", "year", "month", "store_id", "sku").agg(
        # Volume metrics
        spark_sum("units_sold").alias("total_units"),
        spark_sum("demand").alias("total_demand"),
        spark_sum("lost_sales").alias("total_lost_sales"),
        
        # Financial metrics
        spark_round(spark_sum("revenue"), 2).alias("total_revenue"),
        
        # Promo metrics
        spark_sum(when(col("is_promo"), col("units_sold")).otherwise(0)).alias("promo_units"),
        spark_round(spark_sum(when(col("is_promo"), col("revenue")).otherwise(0)), 2).alias("promo_revenue"),
        
        # Stockout metrics
        spark_sum(when(col("stockout_flag"), 1).otherwise(0)).alias("stockout_days"),
        count("*").alias("total_days")
    )
    
    # Add derived metrics
    result = result.withColumn(
        "stockout_rate",
        spark_round(col("stockout_days") / col("total_days") * 100, 2)
    ).withColumn(
        "fill_rate",
        spark_round(col("total_units") / col("total_demand") * 100, 2)
    )
    
    return result


def transform_dim_product_performance(spark: SparkSession):
    """
    Product performance dimension - equivalent to dim_product_performance.sql
    """
    # Load Silver tables
    products = read_silver(spark, "stg_products")
    monthly_sales = spark.read.format("delta").load(f"{GOLD_PATH}/fct_monthly_sales")
    inventory = read_silver(spark, "stg_inventory")
    
    # Sales summary by SKU
    sales_summary = monthly_sales.groupBy("sku").agg(
        spark_sum("total_units").alias("lifetime_units"),
        spark_sum("total_revenue").alias("lifetime_revenue"),
        spark_sum("stockout_days").alias("total_stockout_days"),
        spark_sum("total_days").alias("total_days"),
        countDistinct("store_id").alias("num_stores"),
        spark_min("month_start").alias("first_sale_date"),
        spark_max("month_start").alias("last_sale_date"),
        avg("fill_rate").alias("avg_fill_rate")
    )
    
    # Inventory summary by SKU
    inventory_summary = inventory.groupBy("sku").agg(
        avg("on_hand_qty").alias("avg_on_hand"),
        avg("inventory_value").alias("avg_inventory_value"),
        spark_sum(when(col("is_stockout"), 1).otherwise(0)).alias("stockout_snapshots"),
        count("*").alias("total_snapshots")
    )
    
    # Join all together
    result = products.alias("p") \
        .join(sales_summary.alias("s"), "sku", "left") \
        .join(inventory_summary.alias("i"), "sku", "left") \
        .select(
            col("p.sku"),
            col("p.product_name"),
            col("p.category"),
            col("p.abc_class"),
            col("p.unit_cost"),
            col("p.unit_price"),
            col("p.margin_pct"),
            
            # Sales metrics
            coalesce(col("s.lifetime_units"), lit(0)).alias("lifetime_units"),
            coalesce(col("s.lifetime_revenue"), lit(0)).alias("lifetime_revenue"),
            coalesce(col("s.num_stores"), lit(0)).alias("num_stores"),
            col("s.first_sale_date"),
            col("s.last_sale_date"),
            coalesce(col("s.avg_fill_rate"), lit(0)).alias("avg_fill_rate"),
            
            # Inventory metrics
            coalesce(col("i.avg_on_hand"), lit(0)).alias("avg_on_hand"),
            coalesce(col("i.avg_inventory_value"), lit(0)).alias("avg_inventory_value"),
            
            # Service level
            spark_round(
                coalesce(col("s.total_stockout_days"), lit(0)) * 100.0 / 
                col("s.total_days"), 2
            ).alias("stockout_rate"),
            spark_round(
                100 - coalesce(col("s.total_stockout_days"), lit(0)) * 100.0 / 
                col("s.total_days"), 2
            ).alias("service_level"),
            
            # Inventory health
            spark_round(
                coalesce(col("i.stockout_snapshots"), lit(0)) * 100.0 / 
                col("i.total_snapshots"), 2
            ).alias("inventory_stockout_rate"),
            
            current_timestamp().alias("_loaded_at")
        )
    
    return result


def run_gold_transformations():
    """Run all Gold transformations"""
    print("=" * 60)
    print("GOLD LAYER TRANSFORMATIONS (PySpark)")
    print("=" * 60)
    print(f"Source: {SILVER_PATH}")
    print(f"Target: {GOLD_PATH}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    os.makedirs(GOLD_PATH, exist_ok=True)
    
    spark = create_spark_session()
    print(f"Spark version: {spark.version}\n")
    
    print("Running transformations...")
    
    # Weekly sales (no dependencies)
    fct_weekly = transform_fct_weekly_sales(spark)
    write_gold(fct_weekly, "fct_weekly_sales")
    
    # Monthly sales (no dependencies)
    fct_monthly = transform_fct_monthly_sales(spark)
    write_gold(fct_monthly, "fct_monthly_sales")
    
    # Product performance (depends on fct_monthly_sales)
    dim_product = transform_dim_product_performance(spark)
    write_gold(dim_product, "dim_product_performance")
    
    print("\n" + "=" * 60)
    print("✅ GOLD LAYER COMPLETE (PySpark)")
    print("=" * 60)
    
    spark.stop()


if __name__ == "__main__":
    run_gold_transformations()
