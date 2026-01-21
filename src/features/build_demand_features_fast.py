"""
Demand Feature Engineering - DuckDB Native (FAST)
Uses SQL window functions - 10-50x faster than pandas for large data
"""
import duckdb
from pathlib import Path

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"


def main():
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS main_features")
    
    print("Building features with DuckDB window functions...")
    
    con.execute("""
        DROP TABLE IF EXISTS main_features.demand_features;
        
        CREATE TABLE main_features.demand_features AS
        WITH base AS (
            SELECT 
                date as ds,
                sku,
                store_id,
                units_sold,
                demand,
                revenue,
                is_promo,
                stockout_flag,
                day_of_week,
                month,
                year
            FROM main_silver.stg_sales
        ),
        with_lags AS (
            SELECT *,
                -- Lag features
                LAG(units_sold, 7) OVER w AS units_sold_lag_7,
                LAG(units_sold, 14) OVER w AS units_sold_lag_14,
                LAG(units_sold, 30) OVER w AS units_sold_lag_30,
                
                -- Rolling 7-day (exclude current row: BETWEEN 7 PRECEDING AND 1 PRECEDING)
                AVG(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS units_sold_roll_mean_7,
                STDDEV(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS units_sold_roll_std_7,
                MIN(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS units_sold_roll_min_7,
                MAX(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS units_sold_roll_max_7,
                
                -- Rolling 14-day
                AVG(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS units_sold_roll_mean_14,
                STDDEV(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS units_sold_roll_std_14,
                MIN(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS units_sold_roll_min_14,
                MAX(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS units_sold_roll_max_14,
                
                -- Rolling 30-day
                AVG(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS units_sold_roll_mean_30,
                STDDEV(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS units_sold_roll_std_30,
                MIN(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS units_sold_roll_min_30,
                MAX(units_sold) OVER (PARTITION BY sku, store_id ORDER BY ds ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS units_sold_roll_max_30
                
            FROM base
            WINDOW w AS (PARTITION BY sku, store_id ORDER BY ds)
        ),
        with_calendar AS (
            SELECT *,
                CASE WHEN day_of_week IN (6, 7) THEN 1 ELSE 0 END AS is_weekend,
                ((month - 1) // 3) + 1 AS quarter
            FROM with_lags
        ),
        with_aggs AS (
            SELECT 
                wc.*,
                sku_agg.sku_total_qty,
                store_agg.store_total_qty
            FROM with_calendar wc
            LEFT JOIN (
                SELECT sku, ds, SUM(units_sold) AS sku_total_qty
                FROM base GROUP BY sku, ds
            ) sku_agg ON wc.sku = sku_agg.sku AND wc.ds = sku_agg.ds
            LEFT JOIN (
                SELECT store_id, ds, SUM(units_sold) AS store_total_qty
                FROM base GROUP BY store_id, ds
            ) store_agg ON wc.store_id = store_agg.store_id AND wc.ds = store_agg.ds
        )
        SELECT * FROM with_aggs
        WHERE units_sold_lag_7 IS NOT NULL
    """)
    
    # Stats
    count = con.execute("SELECT COUNT(*) FROM main_features.demand_features").fetchone()[0]
    print(f"Created {count:,} rows")
    
    print("\nSample:")
    print(con.execute("SELECT * FROM main_features.demand_features LIMIT 3").df().to_string())
    
    print("\nColumns:")
    print(con.execute("DESCRIBE main_features.demand_features").df()["column_name"].tolist())
    
    con.close()
    print("\nDone!")


if __name__ == "__main__":
    main()