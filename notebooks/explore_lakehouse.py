"""
Lakehouse Exploration Script
Queries local Delta Lake Bronze layer and DuckDB warehouse.
"""
import duckdb
from pathlib import Path

BRONZE_PATH = Path("C:/Users/Manu/supply_chain_project/data/bronze")
WAREHOUSE_PATH = Path("C:/Users/Manu/supply_chain_project/data/warehouse.duckdb")


def explore_bronze():
    """Explore Bronze layer (Local Delta Lake)"""
    print("=" * 60)
    print("BRONZE LAYER (Local Delta Lake)")
    print("=" * 60)
    print(f"Path: {BRONZE_PATH}")
    print()
    
    con = duckdb.connect()
    
    tables = ["suppliers", "products", "locations", "carriers", "sales", 
              "inventory", "demand_forecasts", "purchase_orders", "shipments"]
    
    for table in tables:
        table_path = BRONZE_PATH / table
        if table_path.exists():
            result = con.execute(f"""
                SELECT COUNT(*) as cnt 
                FROM delta_scan('{table_path}')
            """).fetchone()
            print(f"  {table}: {result[0]:,} rows")
        else:
            print(f"  {table}: NOT FOUND")
    
    # Sample query
    print("\nProducts by ABC Class:")
    print(con.execute(f"""
        SELECT abc_class, COUNT(*) as cnt
        FROM delta_scan('{BRONZE_PATH}/products')
        GROUP BY abc_class
        ORDER BY abc_class
    """).df())


def explore_warehouse():
    """Explore DuckDB Warehouse (Silver/Gold)"""
    print("\n" + "=" * 60)
    print("WAREHOUSE (DuckDB - Silver/Gold)")
    print("=" * 60)
    print(f"Path: {WAREHOUSE_PATH}")
    print()
    
    if not WAREHOUSE_PATH.exists():
        print("⚠️  Warehouse not found. Run dbt first:")
        print("   cd dbt_project && dbt run")
        return
    
    con = duckdb.connect(str(WAREHOUSE_PATH))
    
    # List tables by schema
    for schema in ['silver', 'gold']:
        try:
            tables = con.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{schema}'
            """).fetchall()
            
            if tables:
                print(f"\n{schema.upper()} tables:")
                for t in tables:
                    count = con.execute(f"SELECT COUNT(*) FROM {schema}.{t[0]}").fetchone()[0]
                    print(f"  {t[0]}: {count:,} rows")
        except:
            print(f"\n{schema.upper()}: No tables found")
    
    # Sample query
    try:
        print("\n--- Sample: Monthly Revenue Trend ---")
        print(con.execute("""
            SELECT 
                month_start,
                ROUND(SUM(total_revenue), 2) as revenue,
                SUM(total_units) as units
            FROM gold.fct_monthly_sales
            GROUP BY month_start
            ORDER BY month_start
            LIMIT 12
        """).df())
    except Exception as e:
        print(f"Gold tables not available: {e}")


def run_sample_queries():
    """Run analytical queries on Bronze layer"""
    print("\n" + "=" * 60)
    print("SAMPLE ANALYTICS (Bronze Layer)")
    print("=" * 60)
    
    con = duckdb.connect()
    
    # Revenue by Category
    print("\n--- Revenue by Category ---")
    print(con.execute(f"""
        SELECT 
            p.category,
            ROUND(SUM(s.revenue), 2) as total_revenue,
            SUM(s.units_sold) as total_units
        FROM delta_scan('{BRONZE_PATH}/sales') s
        JOIN delta_scan('{BRONZE_PATH}/products') p ON s.sku = p.sku
        GROUP BY p.category
        ORDER BY total_revenue DESC
        LIMIT 10
    """).df())
    
    # Monthly trend
    print("\n--- Monthly Sales Trend ---")
    print(con.execute(f"""
        SELECT 
            DATE_TRUNC('month', date) as month,
            ROUND(SUM(revenue), 2) as revenue,
            SUM(units_sold) as units,
            SUM(CASE WHEN stockout_flag THEN 1 ELSE 0 END) as stockout_events
        FROM delta_scan('{BRONZE_PATH}/sales')
        GROUP BY 1
        ORDER BY 1
        LIMIT 12
    """).df())
    
    # Supplier performance
    print("\n--- Supplier Performance (by delay) ---")
    print(con.execute(f"""
        SELECT 
            supplier_id,
            COUNT(*) as total_pos,
            ROUND(AVG(delay_days), 1) as avg_delay,
            SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) as delayed_pos
        FROM delta_scan('{BRONZE_PATH}/purchase_orders')
        WHERE delay_days IS NOT NULL
        GROUP BY supplier_id
        ORDER BY avg_delay DESC
        LIMIT 10
    """).df())


if __name__ == "__main__":
    explore_bronze()
    explore_warehouse()
    run_sample_queries()