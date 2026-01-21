"""
Anomaly Detection - DuckDB Native (FAST)
Uses SQL for statistical anomalies, Python for Isolation Forest
"""
import duckdb
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"


def main():
    con = duckdb.connect(str(DB_PATH))
    
    print("Computing statistical anomalies in DuckDB...")
    
    # Step 1: Compute Z-score and IQR anomalies in SQL
    con.execute("""
        DROP TABLE IF EXISTS main_features.anomalies;
        
        CREATE TABLE main_features.anomalies AS
        WITH stats AS (
            SELECT 
                AVG(units_sold) AS units_mean,
                STDDEV(units_sold) AS units_std,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY units_sold) AS units_q1,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY units_sold) AS units_q3,
                AVG(revenue) AS rev_mean,
                STDDEV(revenue) AS rev_std,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue) AS rev_q1,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue) AS rev_q3
            FROM main_features.demand_features
        ),
        with_anomalies AS (
            SELECT 
                f.*,
                
                -- Demand Z-score anomaly
                CASE WHEN ABS((units_sold - s.units_mean) / NULLIF(s.units_std, 0)) > 3 
                     THEN 1 ELSE 0 END AS anomaly_demand_zscore,
                
                -- Demand IQR anomaly
                CASE WHEN units_sold < (s.units_q1 - 1.5 * (s.units_q3 - s.units_q1))
                       OR units_sold > (s.units_q3 + 1.5 * (s.units_q3 - s.units_q1))
                     THEN 1 ELSE 0 END AS anomaly_demand_iqr,
                
                -- Contextual anomaly (vs rolling mean)
                (units_sold - units_sold_roll_mean_7) / NULLIF(units_sold_roll_std_7, 0) AS demand_deviation,
                CASE WHEN ABS((units_sold - units_sold_roll_mean_7) / NULLIF(units_sold_roll_std_7, 0)) > 2.5
                     THEN 1 ELSE 0 END AS anomaly_demand_contextual,
                
                -- Stockout anomaly
                CAST(stockout_flag AS INTEGER) AS anomaly_stockout,
                
                -- Lost sales ratio
                (demand / NULLIF(units_sold, 0)) - 1 AS lost_sales_ratio,
                CASE WHEN (demand / NULLIF(units_sold, 0)) - 1 > 0.2
                     THEN 1 ELSE 0 END AS anomaly_high_lost_sales,
                
                -- Revenue Z-score anomaly
                CASE WHEN ABS((revenue - s.rev_mean) / NULLIF(s.rev_std, 0)) > 3
                     THEN 1 ELSE 0 END AS anomaly_revenue_zscore,
                
                -- Revenue IQR anomaly
                CASE WHEN revenue < (s.rev_q1 - 1.5 * (s.rev_q3 - s.rev_q1))
                       OR revenue > (s.rev_q3 + 1.5 * (s.rev_q3 - s.rev_q1))
                     THEN 1 ELSE 0 END AS anomaly_revenue_iqr
                
            FROM main_features.demand_features f
            CROSS JOIN stats s
        )
        SELECT * FROM with_anomalies
    """)
    
    print("Running Isolation Forest...")
    
    # Step 2: Load data for Isolation Forest
    df = con.execute("""
        SELECT ds, sku, store_id, units_sold, revenue, demand, 
               units_sold_roll_mean_7, units_sold_roll_std_7
        FROM main_features.anomalies
    """).df()
    
    feature_cols = ["units_sold", "revenue", "demand", "units_sold_roll_mean_7", "units_sold_roll_std_7"]
    X = df[feature_cols].fillna(0)
    
    iso = IsolationForest(contamination=0.05, random_state=42, n_jobs=-1)
    df["anomaly_isolation_forest"] = (iso.fit_predict(X) == -1).astype(int)
    
    # Step 3: Update table with Isolation Forest results
    iso_results = df[["ds", "sku", "store_id", "anomaly_isolation_forest"]]
    con.execute("CREATE TEMP TABLE iso_results AS SELECT * FROM iso_results")
    
    con.execute("""
        ALTER TABLE main_features.anomalies ADD COLUMN IF NOT EXISTS anomaly_isolation_forest INTEGER;
        
        UPDATE main_features.anomalies a
        SET anomaly_isolation_forest = i.anomaly_isolation_forest
        FROM iso_results i
        WHERE a.ds = i.ds AND a.sku = i.sku AND a.store_id = i.store_id
    """)
    
    # Step 4: Add summary columns
    con.execute("""
        ALTER TABLE main_features.anomalies ADD COLUMN IF NOT EXISTS anomaly_score INTEGER;
        ALTER TABLE main_features.anomalies ADD COLUMN IF NOT EXISTS is_anomaly INTEGER;
        
        UPDATE main_features.anomalies
        SET anomaly_score = COALESCE(anomaly_demand_zscore, 0) 
                          + COALESCE(anomaly_demand_iqr, 0)
                          + COALESCE(anomaly_demand_contextual, 0)
                          + COALESCE(anomaly_stockout, 0)
                          + COALESCE(anomaly_high_lost_sales, 0)
                          + COALESCE(anomaly_revenue_zscore, 0)
                          + COALESCE(anomaly_revenue_iqr, 0)
                          + COALESCE(anomaly_isolation_forest, 0);
        
        UPDATE main_features.anomalies
        SET is_anomaly = CASE WHEN anomaly_score >= 2 THEN 1 ELSE 0 END
    """)
    
    # Stats
    print("\nAnomaly counts:")
    stats = con.execute("""
        SELECT 
            SUM(anomaly_demand_zscore) AS demand_zscore,
            SUM(anomaly_demand_iqr) AS demand_iqr,
            SUM(anomaly_demand_contextual) AS demand_contextual,
            SUM(anomaly_stockout) AS stockout,
            SUM(anomaly_high_lost_sales) AS high_lost_sales,
            SUM(anomaly_revenue_zscore) AS revenue_zscore,
            SUM(anomaly_revenue_iqr) AS revenue_iqr,
            SUM(anomaly_isolation_forest) AS isolation_forest,
            SUM(is_anomaly) AS total_anomalies,
            COUNT(*) AS total_rows
        FROM main_features.anomalies
    """).df().iloc[0]
    
    total = stats["total_rows"]
    for col in stats.index[:-1]:
        print(f"  {col}: {int(stats[col]):,} ({stats[col]/total*100:.2f}%)")
    
    print(f"\nTotal flagged (score >= 2): {int(stats['total_anomalies']):,}")
    
    con.close()
    print("Done!")
    print("\nTo generate reports, run: python src/features/export_anomaly_report.py")


if __name__ == "__main__":
    main()
