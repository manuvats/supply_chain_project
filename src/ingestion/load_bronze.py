"""
Bronze Layer Ingestion
Reads raw parquet from Google Drive → Writes Delta Lake locally.
"""
import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime
from deltalake import write_deltalake, DeltaTable

# === CONFIGURATION ===
# Source: Raw data on Google Drive
RAW_DATA_PATH = Path("H:/My Drive/supply_chain_raw")

# Target: Bronze layer LOCAL (Delta Lake works locally)
BRONZE_PATH = Path("C:/Users/Manu/supply_chain_project/data/bronze")

DATE_COLUMNS = {
    "sales": ["date"],
    "demand_forecasts": ["forecast_date"],
    "inventory": ["snapshot_date"],
    "purchase_orders": ["order_date", "expected_date", "actual_date"],
    "shipments": ["planned_ship_date", "actual_ship_date", "planned_delivery_date", "actual_delivery_date"],
    "production_orders": ["planned_date", "completion_date"],
}


def load_parquet(name: str, path: Path) -> pd.DataFrame:
    """Load a parquet file from Google Drive"""
    print(f"  Loading {name} from Google Drive...")
    df = pd.read_parquet(path)
    
    if name in DATE_COLUMNS:
        for col in DATE_COLUMNS[name]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
    
    print(f"    → {len(df):,} rows")
    return df


def write_to_delta(df: pd.DataFrame, name: str, bronze_path: Path):
    """Write DataFrame to local Delta Lake"""
    table_path = bronze_path / name
    table_path.parent.mkdir(parents=True, exist_ok=True)
    
    write_deltalake(
        str(table_path),
        df,
        mode="overwrite"
    )
    
    # Get size
    size_mb = sum(f.stat().st_size for f in table_path.glob("*.parquet")) / 1e6
    print(f"  ✓ {name}: {len(df):,} rows → Delta Lake ({size_mb:.1f} MB)")


def load_bronze_layer():
    """Main ingestion: Google Drive → Local Delta Lake"""
    print("=" * 60)
    print("BRONZE LAYER INGESTION")
    print("=" * 60)
    print(f"Source: {RAW_DATA_PATH} (Google Drive)")
    print(f"Target: {BRONZE_PATH} (Local Delta Lake)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Verify source exists
    if not RAW_DATA_PATH.exists():
        print(f"ERROR: Source path not found: {RAW_DATA_PATH}")
        print("Make sure Google Drive Desktop is running and data is generated.")
        return
    
    BRONZE_PATH.mkdir(parents=True, exist_ok=True)
    
    # All tables to load
    tables = [
        "suppliers", "products", "locations", "carriers", "supplier_product_map",
        "purchase_orders", "shipments", "production_orders",
        "sales", "demand_forecasts", "inventory"
    ]
    
    print("[1/1] Loading all tables...")
    for name in tables:
        source_file = RAW_DATA_PATH / f"{name}.parquet"
        if source_file.exists():
            df = load_parquet(name, source_file)
            write_to_delta(df, name, BRONZE_PATH)
        else:
            print(f"  ⚠ {name}.parquet not found, skipping...")
    
    print("\n" + "=" * 60)
    print("✅ BRONZE LAYER COMPLETE")
    print("=" * 60)


def verify_bronze_layer():
    """Verify Bronze layer with DuckDB"""
    print("\n" + "=" * 60)
    print("VERIFICATION (Delta Lake)")
    print("=" * 60)
    
    con = duckdb.connect()
    
    total_size = 0
    for table_dir in sorted(BRONZE_PATH.iterdir()):
        if table_dir.is_dir() and not table_dir.name.startswith('.'):
            try:
                count = con.execute(f"""
                    SELECT COUNT(*) FROM delta_scan('{table_dir}')
                """).fetchone()[0]
                size_mb = sum(f.stat().st_size for f in table_dir.glob("*.parquet")) / 1e6
                total_size += size_mb
                print(f"  ✓ {table_dir.name}: {count:,} rows ({size_mb:.1f} MB)")
            except Exception as e:
                print(f"  ✗ {table_dir.name}: Error - {e}")
    
    print(f"\nTotal size: {total_size:.1f} MB")


if __name__ == "__main__":
    load_bronze_layer()
    verify_bronze_layer()