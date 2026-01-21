"""
Data Profiler - Analyze missing values and data quality.
"""
import duckdb
import pandas as pd
from pathlib import Path

BRONZE_PATH = Path("C:/Users/Manu/supply_chain_project/data/bronze")


def profile_table(table_name: str):
    """Generate data profile for a Bronze table"""
    table_path = BRONZE_PATH / table_name
    
    if not table_path.exists():
        print(f"Table not found: {table_path}")
        return
    
    con = duckdb.connect()
    
    print("=" * 70)
    print(f"DATA PROFILE: {table_name}")
    print("=" * 70)
    
    # Get row count
    total_rows = con.execute(f"SELECT COUNT(*) FROM delta_scan('{table_path}')").fetchone()[0]
    print(f"\nTotal Rows: {total_rows:,}")
    
    # Get columns
    columns = con.execute(f"DESCRIBE SELECT * FROM delta_scan('{table_path}')").df()
    print(f"Columns: {len(columns)}")
    
    # Profile each column
    print("\n" + "-" * 70)
    print(f"{'Column':<25} {'Type':<15} {'Nulls':>10} {'Null%':>8} {'Unique':>10}")
    print("-" * 70)
    
    results = []
    for _, row in columns.iterrows():
        col_name = row['column_name']
        col_type = row['column_type']
        
        stats = con.execute(f"""
            SELECT 
                SUM(CASE WHEN "{col_name}" IS NULL THEN 1 ELSE 0 END) as nulls,
                COUNT(DISTINCT "{col_name}") as unique_vals
            FROM delta_scan('{table_path}')
        """).fetchone()
        
        null_count = stats[0]
        unique_count = stats[1]
        null_pct = round(100 * null_count / total_rows, 2) if total_rows > 0 else 0
        
        print(f"{col_name:<25} {col_type:<15} {null_count:>10,} {null_pct:>7.2f}% {unique_count:>10,}")
        
        results.append({
            'column': col_name,
            'type': col_type,
            'null_count': null_count,
            'null_pct': null_pct,
            'unique_count': unique_count
        })
    
    return pd.DataFrame(results)


def profile_all_tables():
    """Profile all Bronze tables"""
    tables = [d.name for d in BRONZE_PATH.iterdir() if d.is_dir() and not d.name.startswith('.')]
    
    all_profiles = {}
    for table in sorted(tables):
        profile = profile_table(table)
        all_profiles[table] = profile
        print()
    
    return all_profiles


def analyze_null_patterns(table_name: str, null_column: str, group_by_column: str):
    """Analyze null patterns by grouping"""
    table_path = BRONZE_PATH / table_name
    con = duckdb.connect()
    
    print(f"\nNull Pattern: {null_column} grouped by {group_by_column}")
    print("-" * 50)
    
    result = con.execute(f"""
        SELECT 
            "{group_by_column}",
            COUNT(*) as total,
            SUM(CASE WHEN "{null_column}" IS NULL THEN 1 ELSE 0 END) as nulls,
            ROUND(100.0 * SUM(CASE WHEN "{null_column}" IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as null_pct
        FROM delta_scan('{table_path}')
        GROUP BY "{group_by_column}"
        ORDER BY null_pct DESC
        LIMIT 15
    """).df()
    
    print(result.to_string(index=False))
    return result


def show_null_samples(table_name: str, null_column: str, n: int = 10):
    """Show sample rows where column is null"""
    table_path = BRONZE_PATH / table_name
    con = duckdb.connect()
    
    print(f"\nSample rows where {null_column} IS NULL:")
    print("-" * 50)
    
    result = con.execute(f"""
        SELECT *
        FROM delta_scan('{table_path}')
        WHERE "{null_column}" IS NULL
        LIMIT {n}
    """).df()
    
    print(result.to_string())
    return result


def summary_report():
    """Generate summary of all data quality issues"""
    tables = [d.name for d in BRONZE_PATH.iterdir() if d.is_dir() and not d.name.startswith('.')]
    con = duckdb.connect()
    
    print("=" * 70)
    print("DATA QUALITY SUMMARY")
    print("=" * 70)
    
    issues = []
    
    for table in sorted(tables):
        table_path = BRONZE_PATH / table
        
        # Get columns with nulls
        columns = con.execute(f"DESCRIBE SELECT * FROM delta_scan('{table_path}')").df()
        total_rows = con.execute(f"SELECT COUNT(*) FROM delta_scan('{table_path}')").fetchone()[0]
        
        for _, row in columns.iterrows():
            col_name = row['column_name']
            null_count = con.execute(f"""
                SELECT SUM(CASE WHEN "{col_name}" IS NULL THEN 1 ELSE 0 END)
                FROM delta_scan('{table_path}')
            """).fetchone()[0]
            
            if null_count > 0:
                null_pct = round(100 * null_count / total_rows, 2)
                issues.append({
                    'table': table,
                    'column': col_name,
                    'null_count': null_count,
                    'null_pct': null_pct,
                    'severity': 'HIGH' if null_pct > 10 else ('MEDIUM' if null_pct > 5 else 'LOW')
                })
    
    if issues:
        df = pd.DataFrame(issues).sort_values(['severity', 'null_pct'], ascending=[True, False])
        print("\nColumns with Missing Values:")
        print("-" * 70)
        print(df.to_string(index=False))
        return df
    else:
        print("\n✅ No missing values found!")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        table = sys.argv[1]
        profile_table(table)
    else:
        # Summary report
        summary_report()
        
        # Detailed profile for inventory (the table with issues)
        print("\n")
        profile_table("inventory")
        
        # Analyze patterns
        print("\n")
        analyze_null_patterns("inventory", "snapshot_date", "location_id")
