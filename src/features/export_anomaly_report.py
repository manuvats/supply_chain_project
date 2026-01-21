"""
Anomaly Report Generator
Exports anomaly detection results to Excel and HTML reports
"""
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
REPORTS_DIR = PROJECT_ROOT / "reports"


def get_anomaly_data(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Load anomaly data from DuckDB."""
    return con.execute("SELECT * FROM main_features.anomalies").df()


def get_summary_stats(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Get anomaly summary statistics."""
    return con.execute("""
        SELECT 
            'anomaly_demand_zscore' AS anomaly_type, SUM(anomaly_demand_zscore) AS count
        FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_demand_iqr', SUM(anomaly_demand_iqr) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_demand_contextual', SUM(anomaly_demand_contextual) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_stockout', SUM(anomaly_stockout) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_high_lost_sales', SUM(anomaly_high_lost_sales) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_revenue_zscore', SUM(anomaly_revenue_zscore) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_revenue_iqr', SUM(anomaly_revenue_iqr) FROM main_features.anomalies
        UNION ALL
        SELECT 'anomaly_isolation_forest', SUM(anomaly_isolation_forest) FROM main_features.anomalies
        UNION ALL
        SELECT 'total_flagged (score>=2)', SUM(is_anomaly) FROM main_features.anomalies
    """).df()


def get_top_anomalies(con: duckdb.DuckDBPyConnection, limit: int = 100) -> pd.DataFrame:
    """Get top anomalies by score."""
    return con.execute(f"""
        SELECT ds, sku, store_id, units_sold, demand, revenue,
               anomaly_score, is_anomaly,
               anomaly_demand_zscore, anomaly_demand_iqr, anomaly_demand_contextual,
               anomaly_stockout, anomaly_high_lost_sales,
               anomaly_revenue_zscore, anomaly_revenue_iqr, anomaly_isolation_forest
        FROM main_features.anomalies
        WHERE is_anomaly = 1
        ORDER BY anomaly_score DESC, ds DESC
        LIMIT {limit}
    """).df()


def get_anomalies_by_sku(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Get anomaly counts by SKU."""
    return con.execute("""
        SELECT sku,
               COUNT(*) AS total_records,
               SUM(is_anomaly) AS anomaly_count,
               ROUND(SUM(is_anomaly) * 100.0 / COUNT(*), 2) AS anomaly_pct
        FROM main_features.anomalies
        GROUP BY sku
        ORDER BY anomaly_count DESC
        LIMIT 50
    """).df()


def get_anomalies_by_store(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Get anomaly counts by store."""
    return con.execute("""
        SELECT store_id,
               COUNT(*) AS total_records,
               SUM(is_anomaly) AS anomaly_count,
               ROUND(SUM(is_anomaly) * 100.0 / COUNT(*), 2) AS anomaly_pct
        FROM main_features.anomalies
        GROUP BY store_id
        ORDER BY anomaly_count DESC
        LIMIT 50
    """).df()


def get_anomalies_by_date(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Get anomaly counts by date."""
    return con.execute("""
        SELECT CAST(ds AS DATE) AS date,
               COUNT(*) AS total_records,
               SUM(is_anomaly) AS anomaly_count
        FROM main_features.anomalies
        GROUP BY CAST(ds AS DATE)
        ORDER BY date
    """).df()


def export_to_excel(con: duckdb.DuckDBPyConnection, output_path: Path):
    """Export anomaly report to Excel with multiple sheets."""
    print(f"Exporting to Excel: {output_path}")
    
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Summary
        get_summary_stats(con).to_excel(writer, sheet_name="Summary", index=False)
        
        # Top anomalies
        get_top_anomalies(con).to_excel(writer, sheet_name="Top Anomalies", index=False)
        
        # By SKU
        get_anomalies_by_sku(con).to_excel(writer, sheet_name="By SKU", index=False)
        
        # By Store
        get_anomalies_by_store(con).to_excel(writer, sheet_name="By Store", index=False)
        
        # By Date
        get_anomalies_by_date(con).to_excel(writer, sheet_name="By Date", index=False)
    
    print(f"  Created: {output_path}")


def export_to_html(con: duckdb.DuckDBPyConnection, output_path: Path):
    """Export anomaly report to HTML."""
    print(f"Exporting to HTML: {output_path}")
    
    summary = get_summary_stats(con)
    top_anomalies = get_top_anomalies(con, limit=50)
    by_sku = get_anomalies_by_sku(con)
    by_store = get_anomalies_by_store(con)
    by_date = get_anomalies_by_date(con)
    
    total_records = con.execute("SELECT COUNT(*) FROM main_features.anomalies").fetchone()[0]
    total_anomalies = con.execute("SELECT SUM(is_anomaly) FROM main_features.anomalies").fetchone()[0]
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Anomaly Detection Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #4CAF50; }}
        .metric-label {{ font-size: 14px; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; background: white; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:hover {{ background: #f1f1f1; }}
        .timestamp {{ color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>🔍 Anomaly Detection Report</h1>
    <p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <div class="summary-box">
        <div class="metric">
            <div class="metric-value">{total_records:,}</div>
            <div class="metric-label">Total Records</div>
        </div>
        <div class="metric">
            <div class="metric-value">{total_anomalies:,}</div>
            <div class="metric-label">Anomalies Detected</div>
        </div>
        <div class="metric">
            <div class="metric-value">{total_anomalies/total_records*100:.2f}%</div>
            <div class="metric-label">Anomaly Rate</div>
        </div>
    </div>
    
    <h2>📊 Anomaly Summary by Type</h2>
    {summary.to_html(index=False, classes='summary-table')}
    
    <h2>🏪 Top Anomalous Stores</h2>
    {by_store.head(20).to_html(index=False)}
    
    <h2>📦 Top Anomalous SKUs</h2>
    {by_sku.head(20).to_html(index=False)}
    
    <h2>🚨 Top Anomalies (by score)</h2>
    {top_anomalies.head(30).to_html(index=False)}
    
</body>
</html>
"""
    
    output_path.write_text(html, encoding="utf-8")
    print(f"  Created: {output_path}")


def export_to_csv(con: duckdb.DuckDBPyConnection, output_dir: Path):
    """Export anomaly data to CSV files."""
    print(f"Exporting to CSV: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Full anomaly data (only flagged)
    flagged = con.execute("""
        SELECT * FROM main_features.anomalies WHERE is_anomaly = 1
    """).df()
    flagged.to_csv(output_dir / "anomalies_flagged.csv", index=False)
    print(f"  Created: anomalies_flagged.csv ({len(flagged):,} rows)")
    
    # Summary
    get_summary_stats(con).to_csv(output_dir / "anomalies_summary.csv", index=False)
    print(f"  Created: anomalies_summary.csv")
    
    # By date (for time series analysis)
    get_anomalies_by_date(con).to_csv(output_dir / "anomalies_by_date.csv", index=False)
    print(f"  Created: anomalies_by_date.csv")


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    con = duckdb.connect(str(DB_PATH))
    
    # Excel report
    export_to_excel(con, REPORTS_DIR / f"anomaly_report_{timestamp}.xlsx")
    
    # HTML report
    export_to_html(con, REPORTS_DIR / f"anomaly_report_{timestamp}.html")
    
    # CSV exports
    export_to_csv(con, REPORTS_DIR / "csv")
    
    con.close()
    
    print(f"\n✅ All reports saved to: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
