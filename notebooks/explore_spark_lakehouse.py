"""
Explore PySpark Lakehouse
Query and compare Pandas/dbt vs PySpark outputs.
"""
import duckdb
from pathlib import Path

# Paths
BRONZE_PANDAS = Path("C:/Users/Manu/supply_chain_project/data/bronze")
BRONZE_SPARK = Path("C:/Users/Manu/supply_chain_project/data/bronze_spark")
SILVER_SPARK = Path("C:/Users/Manu/supply_chain_project/data/silver_spark")
GOLD_SPARK = Path("C:/Users/Manu/supply_chain_project/data/gold_spark")
WAREHOUSE_DBT = Path("C:/Users/Manu/supply_chain_project/data/warehouse.duckdb")


def compare_bronze_layers():
    """Compare Pandas vs Spark Bronze outputs"""
    print("=" * 60)
    print("BRONZE LAYER COMPARISON")
    print("=" * 60)
    print(f"{'Table':<25} {'Pandas':>15} {'Spark':>15} {'Match':>10}")
    print("-" * 60)
    
    con = duckdb.connect()
    
    tables = ["suppliers", "products", "locations", "sales", "inventory"]
    
    for table in tables:
        pandas_path = BRONZE_PANDAS / table
        spark_path = BRONZE_SPARK / table
        
        pandas_count = 0
        spark_count = 0
        
        if pandas_path.exists():
            pandas_count = con.execute(f"SELECT COUNT(*) FROM delta_scan('{pandas_path}')").fetchone()[0]
        
        if spark_path.exists():
            spark_count = con.execute(f"SELECT COUNT(*) FROM delta_scan('{spark_path}')").fetchone()[0]
        
        match = "✓" if pandas_count == spark_count else "✗"
        print(f"{table:<25} {pandas_count:>15,} {spark_count:>15,} {match:>10}")


def explore_spark_silver():
    """Explore Spark Silver layer"""
    print("\n" + "=" * 60)
    print("SILVER LAYER (PySpark)")
    print("=" * 60)
    print(f"Path: {SILVER_SPARK}")
    print()
    
    con = duckdb.connect()
    
    if not SILVER_SPARK.exists():
        print("⚠️ Silver layer not found. Run transform_silver_spark.py first.")
        return
    
    for table_dir in sorted(SILVER_SPARK.iterdir()):
        if table_dir.is_dir() and not table_dir.name.startswith('.'):
            try:
                count = con.execute(f"SELECT COUNT(*) FROM delta_scan('{table_dir}')").fetchone()[0]
                print(f"  {table_dir.name}: {count:,} rows")
            except Exception as e:
                print(f"  {table_dir.name}: Error - {e}")


def explore_spark_gold():
    """Explore Spark Gold layer"""
    print("\n" + "=" * 60)
    print("GOLD LAYER (PySpark)")
    print("=" * 60)
    print(f"Path: {GOLD_SPARK}")
    print()
    
    con = duckdb.connect()
    
    if not GOLD_SPARK.exists():
        print("⚠️ Gold layer not found. Run transform_gold_spark.py first.")
        return
    
    for table_dir in sorted(GOLD_SPARK.iterdir()):
        if table_dir.is_dir() and not table_dir.name.startswith('.'):
            try:
                count = con.execute(f"SELECT COUNT(*) FROM delta_scan('{table_dir}')").fetchone()[0]
                print(f"  {table_dir.name}: {count:,} rows")
            except Exception as e:
                print(f"  {table_dir.name}: Error - {e}")


def compare_gold_outputs():
    """Compare dbt vs Spark Gold outputs"""
    print("\n" + "=" * 60)
    print("GOLD LAYER COMPARISON (dbt vs Spark)")
    print("=" * 60)
    
    con_dbt = duckdb.connect(str(WAREHOUSE_DBT)) if WAREHOUSE_DBT.exists() else None
    con_spark = duckdb.connect()
    
    if not con_dbt:
        print("⚠️ dbt warehouse not found.")
        return
    
    comparisons = [
        ("fct_weekly_sales", "main_gold.fct_weekly_sales", GOLD_SPARK / "fct_weekly_sales"),
        ("fct_monthly_sales", "main_gold.fct_monthly_sales", GOLD_SPARK / "fct_monthly_sales"),
        ("dim_product_performance", "main_gold.dim_product_performance", GOLD_SPARK / "dim_product_performance"),
    ]
    
    print(f"{'Table':<30} {'dbt':>15} {'Spark':>15} {'Match':>10}")
    print("-" * 70)
    
    for name, dbt_table, spark_path in comparisons:
        dbt_count = 0
        spark_count = 0
        
        try:
            dbt_count = con_dbt.execute(f"SELECT COUNT(*) FROM {dbt_table}").fetchone()[0]
        except:
            pass
        
        if spark_path.exists():
            try:
                spark_count = con_spark.execute(f"SELECT COUNT(*) FROM delta_scan('{spark_path}')").fetchone()[0]
            except:
                pass
        
        match = "✓" if dbt_count == spark_count else "~"  # ~ means close but may differ slightly
        print(f"{name:<30} {dbt_count:>15,} {spark_count:>15,} {match:>10}")


def sample_queries():
    """Run sample queries on Spark Gold layer"""
    print("\n" + "=" * 60)
    print("SAMPLE QUERIES (Spark Gold)")
    print("=" * 60)
    
    con = duckdb.connect()
    
    if not GOLD_SPARK.exists():
        print("⚠️ Spark Gold layer not found.")
        return
    
    # Monthly revenue trend
    print("\n--- Monthly Revenue Trend ---")
    try:
        result = con.execute(f"""
            SELECT 
                month_start,
                ROUND(SUM(total_revenue), 2) as revenue,
                SUM(total_units) as units
            FROM delta_scan('{GOLD_SPARK}/fct_monthly_sales')
            GROUP BY month_start
            ORDER BY month_start
            LIMIT 12
        """).df()
        print(result.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")
    
    # Top products by revenue
    print("\n--- Top 10 Products by Revenue ---")
    try:
        result = con.execute(f"""
            SELECT 
                sku,
                product_name,
                abc_class,
                lifetime_revenue,
                service_level
            FROM delta_scan('{GOLD_SPARK}/dim_product_performance')
            ORDER BY lifetime_revenue DESC
            LIMIT 10
        """).df()
        print(result.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    compare_bronze_layers()
    explore_spark_silver()
    explore_spark_gold()
    compare_gold_outputs()
    sample_queries()
