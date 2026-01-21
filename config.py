"""
Supply Chain Project Configuration
- Raw data: Google Drive
- Bronze/Silver/Gold: Local (Delta Lake)
"""
from pathlib import Path

# === PATHS ===
# Source (Google Drive)
RAW_DATA_PATH = Path("H:/My Drive/supply_chain_raw")

# Local project
PROJECT_PATH = Path("C:/Users/Manu/supply_chain_project")

# Data layers (LOCAL - Delta Lake)
BRONZE_PATH = PROJECT_PATH / "data" / "bronze"
SILVER_PATH = PROJECT_PATH / "data" / "silver"
GOLD_PATH = PROJECT_PATH / "data" / "gold"

# DuckDB warehouse (LOCAL)
WAREHOUSE_PATH = PROJECT_PATH / "data" / "warehouse.duckdb"

# === DATE COLUMNS ===
DATE_COLUMNS = {
    "sales": ["date"],
    "demand_forecasts": ["forecast_date"],
    "inventory": ["snapshot_date"],
    "purchase_orders": ["order_date", "expected_date", "actual_date"],
    "shipments": ["planned_ship_date", "actual_ship_date", "planned_delivery_date", "actual_delivery_date"],
    "production_orders": ["planned_date", "completion_date"],
}

# === VALIDATION THRESHOLDS ===
QUALITY_THRESHOLDS = {
    "max_null_pct": 0.10,
    "max_duplicate_pct": 0.02,
}