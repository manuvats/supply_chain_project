"""
Project Setup Script
Run this first to create directory structure and verify data access.
"""
import os
import sys
from pathlib import Path

# === CONFIGURATION ===
RAW_DATA_PATH = Path("H:/My Drive/supply_chain_enterprise")
PROJECT_PATH = Path("C:/Users/Manu/supply_chain_project")

def create_directories():
    """Create project directory structure"""
    dirs = [
        PROJECT_PATH / "data" / "bronze",
        PROJECT_PATH / "data" / "silver",
        PROJECT_PATH / "data" / "gold",
        PROJECT_PATH / "src" / "ingestion",
        PROJECT_PATH / "src" / "quality",
        PROJECT_PATH / "src" / "utils",
        PROJECT_PATH / "pipelines",
        PROJECT_PATH / "notebooks",
        PROJECT_PATH / "tests",
        PROJECT_PATH / "logs",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d}")

def verify_raw_data():
    """Check if raw data is accessible"""
    expected_files = [
        "suppliers.parquet",
        "products.parquet",
        "locations.parquet",
        "carriers.parquet",
        "supplier_product_map.parquet",
        "purchase_orders.parquet",
        "shipments.parquet",
        "production_orders.parquet",
    ]
    
    expected_dirs = ["sales", "demand_forecasts", "inventory"]
    
    print("\nVerifying raw data access...")
    all_ok = True
    
    for f in expected_files:
        path = RAW_DATA_PATH / f
        if path.exists():
            size_mb = path.stat().st_size / 1e6
            print(f"  ✓ {f} ({size_mb:.1f} MB)")
        else:
            print(f"  ✗ {f} NOT FOUND")
            all_ok = False
    
    for d in expected_dirs:
        path = RAW_DATA_PATH / d
        if path.exists() and path.is_dir():
            n_files = len(list(path.glob("*.parquet")))
            print(f"  ✓ {d}/ ({n_files} files)")
        else:
            print(f"  ✗ {d}/ NOT FOUND")
            all_ok = False
    
    return all_ok

def create_requirements():
    """Create requirements.txt"""
    requirements = """# Supply Chain Project Dependencies
pandas>=2.0.0
pyarrow>=14.0.0
duckdb>=0.9.0
deltalake>=0.14.0
dbt-duckdb>=1.7.0
great-expectations>=0.18.0
prefect>=2.14.0
python-dotenv>=1.0.0
jupyter>=1.0.0
plotly>=5.18.0
streamlit>=1.29.0
"""
    
    req_path = PROJECT_PATH / "requirements.txt"
    req_path.write_text(requirements)
    print(f"\n✓ Created {req_path}")

def create_gitignore():
    """Create .gitignore"""
    gitignore = """# Data
data/
*.parquet
*.duckdb
*.duckdb.wal

# Python
__pycache__/
*.py[cod]
venv/
.venv/
*.egg-info/

# dbt
dbt_project/target/
dbt_project/dbt_packages/
dbt_project/logs/

# Great Expectations
great_expectations/uncommitted/

# IDE
.vscode/
.idea/

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db
"""
    
    gitignore_path = PROJECT_PATH / ".gitignore"
    gitignore_path.write_text(gitignore)
    print(f"✓ Created {gitignore_path}")

def main():
    print("=" * 60)
    print("SUPPLY CHAIN PROJECT SETUP")
    print("=" * 60)
    
    print(f"\nProject path: {PROJECT_PATH}")
    print(f"Raw data path: {RAW_DATA_PATH}")
    
    print("\nCreating directories...")
    create_directories()
    
    if not verify_raw_data():
        print("\n⚠️  Some raw data files are missing!")
        print("Make sure Google Drive Desktop is synced.")
        sys.exit(1)
    
    create_requirements()
    create_gitignore()
    
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. cd C:\\Users\\Manu\\supply_chain_project")
    print("2. python -m venv venv")
    print("3. venv\\Scripts\\activate")
    print("4. pip install -r requirements.txt")
    print("5. python src/ingestion/load_bronze.py")

if __name__ == "__main__":
    main()
