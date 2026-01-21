"""Phase 4 LLM Integration - Configuration"""
import os
from pathlib import Path

# LLM Provider Config (Groq default, OpenAI-compatible)
LLM_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

# For Ollama local: LLM_BASE_URL=http://localhost:11434/v1, LLM_MODEL=llama3.1:8b

# Project Paths - UPDATE THESE TO YOUR LOCAL PATHS
PROJECT_ROOT = Path(os.getenv("QUANTUM_BRICKS_ROOT", r"C:\Users\Manu\supply_chain_project"))
DUCKDB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"

# Schema Reference (for Text-to-SQL)
SCHEMA_INFO = """
Available tables in DuckDB warehouse:

1. main_features.demand_features
   - ds (DATE): date
   - sku (VARCHAR): product SKU
   - store_id (VARCHAR): store identifier
   - units_sold (INTEGER): units sold
   - revenue (DECIMAL): revenue
   - demand (INTEGER): demand quantity
   - units_sold_lag_7, units_sold_lag_14, units_sold_lag_30 (INTEGER): lag features
   - units_sold_roll_mean_7, units_sold_roll_mean_14, units_sold_roll_std_7 (DECIMAL): rolling statistics
   - day_of_week, month, is_weekend (INTEGER): calendar features

2. main_features.anomalies
   - ds, sku, store_id
   - anomaly_score (DECIMAL)
   - is_anomaly (BOOLEAN)
   - anomaly_type (VARCHAR): zscore, iqr, contextual, isolation_forest

3. gold layer tables (main schema):
   - daily_summary, sku_summary, store_summary
"""
