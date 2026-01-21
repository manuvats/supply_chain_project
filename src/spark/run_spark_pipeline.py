"""
Supply Chain ETL Pipeline - PySpark Version
Runs the full Bronze → Silver → Gold pipeline.

Equivalent to: dbt run (but using PySpark)
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_PATH = Path("C:/Users/Manu/supply_chain_project")
SPARK_SCRIPTS = PROJECT_PATH / "src" / "spark"


def run_script(script_name: str, description: str) -> bool:
    """Run a Python script and return success status"""
    script_path = SPARK_SCRIPTS / script_name
    
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print(f"Script: {script_path}")
    print("="*60)
    
    start_time = datetime.now()
    
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False,
        text=True
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if result.returncode == 0:
        print(f"\n✅ {description} completed in {elapsed:.1f}s")
        return True
    else:
        print(f"\n❌ {description} failed after {elapsed:.1f}s")
        return False


def run_pipeline(skip_bronze: bool = False):
    """Run the full ETL pipeline"""
    print("="*60)
    print("SUPPLY CHAIN ETL PIPELINE (PySpark)")
    print("="*60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    steps = []
    
    if not skip_bronze:
        steps.extend([
            ("load_bronze_spark.py", "Bronze Layer Ingestion"),
            ("validate_bronze_spark.py", "Bronze Data Validation"),
        ])
    
    steps.extend([
        ("transform_silver_spark.py", "Silver Layer Transformations"),
        ("transform_gold_spark.py", "Gold Layer Transformations"),
    ])
    
    results = {}
    
    for script_name, description in steps:
        success = run_script(script_name, description)
        results[description] = success
        
        if not success:
            print(f"\n⚠️ Pipeline stopped due to failure in: {description}")
            break
    
    # Summary
    print("\n" + "="*60)
    print("PIPELINE SUMMARY")
    print("="*60)
    
    for step, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {step}")
    
    all_success = all(results.values())
    
    if all_success:
        print("\n✅ PIPELINE COMPLETED SUCCESSFULLY")
    else:
        print("\n❌ PIPELINE COMPLETED WITH ERRORS")
    
    return all_success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Supply Chain ETL Pipeline (PySpark)")
    parser.add_argument("--skip-bronze", action="store_true", 
                        help="Skip Bronze layer (use existing data)")
    parser.add_argument("--silver-only", action="store_true",
                        help="Run only Silver transformations")
    parser.add_argument("--gold-only", action="store_true",
                        help="Run only Gold transformations")
    
    args = parser.parse_args()
    
    if args.silver_only:
        run_script("transform_silver_spark.py", "Silver Layer Transformations")
    elif args.gold_only:
        run_script("transform_gold_spark.py", "Gold Layer Transformations")
    else:
        success = run_pipeline(skip_bronze=args.skip_bronze)
        exit(0 if success else 1)
