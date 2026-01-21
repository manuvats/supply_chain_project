"""
Data Quality Validation - PySpark Version
Validates Bronze layer data using Spark.

Parallel implementation to validate_bronze.py (DuckDB version)
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, countDistinct, sum as spark_sum, when
from datetime import datetime
import os

# === CONFIGURATION ===
BRONZE_PATH = "C:/Users/Manu/supply_chain_project/data/bronze_spark"


def create_spark_session():
    """Create SparkSession with Delta Lake support"""
    spark = SparkSession.builder \
        .appName("SupplyChain-Validation") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


class SparkDataQualityChecker:
    def __init__(self, spark: SparkSession, bronze_path: str):
        self.spark = spark
        self.bronze_path = bronze_path
        self.results = []
    
    def read_table(self, table_name: str):
        """Read Delta table"""
        return self.spark.read.format("delta").load(f"{self.bronze_path}/{table_name}")
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        path = f"{self.bronze_path}/{table_name}"
        exists = os.path.isdir(path)
        self.results.append({
            "table": table_name,
            "check": "exists",
            "passed": exists,
            "details": "Delta table" if exists else "NOT FOUND"
        })
        return exists
    
    def check_row_count(self, table_name: str, min_rows: int = 1) -> bool:
        """Check minimum row count"""
        df = self.read_table(table_name)
        row_count = df.count()
        
        passed = row_count >= min_rows
        self.results.append({
            "table": table_name,
            "check": "row_count",
            "passed": passed,
            "details": f"{row_count:,} rows (min: {min_rows:,})"
        })
        return passed
    
    def check_null_percentage(self, table_name: str, column: str, max_pct: float = 0.1) -> bool:
        """Check null percentage in column"""
        df = self.read_table(table_name)
        
        stats = df.agg(
            count("*").alias("total"),
            spark_sum(when(col(column).isNull(), 1).otherwise(0)).alias("nulls")
        ).collect()[0]
        
        total, nulls = stats["total"], stats["nulls"]
        null_pct = nulls / total if total > 0 else 0
        passed = null_pct <= max_pct
        
        self.results.append({
            "table": table_name,
            "check": f"null_pct({column})",
            "passed": passed,
            "details": f"{null_pct:.2%} nulls (max: {max_pct:.0%})"
        })
        return passed
    
    def check_unique(self, table_name: str, column: str) -> bool:
        """Check column uniqueness"""
        df = self.read_table(table_name)
        
        stats = df.agg(
            count("*").alias("total"),
            countDistinct(col(column)).alias("unique")
        ).collect()[0]
        
        total, unique = stats["total"], stats["unique"]
        passed = total == unique
        
        self.results.append({
            "table": table_name,
            "check": f"unique({column})",
            "passed": passed,
            "details": f"{unique:,} unique / {total:,} total"
        })
        return passed
    
    def check_referential_integrity(self, table_name: str, column: str,
                                     ref_table: str, ref_column: str) -> bool:
        """Check foreign key references exist"""
        df = self.read_table(table_name)
        ref_df = self.read_table(ref_table)
        
        # Left join and count orphans
        orphans = df.alias("t") \
            .join(ref_df.alias("r"), col(f"t.{column}") == col(f"r.{ref_column}"), "left") \
            .filter(col(f"r.{ref_column}").isNull() & col(f"t.{column}").isNotNull()) \
            .count()
        
        passed = orphans == 0
        
        self.results.append({
            "table": table_name,
            "check": f"ref({column}→{ref_table}.{ref_column})",
            "passed": passed,
            "details": f"{orphans:,} orphan records"
        })
        return passed
    
    def check_value_range(self, table_name: str, column: str,
                          min_val: float = None, max_val: float = None) -> bool:
        """Check values are within expected range"""
        df = self.read_table(table_name)
        
        condition = None
        if min_val is not None:
            condition = col(column) < min_val
        if max_val is not None:
            cond = col(column) > max_val
            condition = cond if condition is None else (condition | cond)
        
        out_of_range = df.filter(condition).count() if condition else 0
        passed = out_of_range == 0
        
        self.results.append({
            "table": table_name,
            "check": f"range({column})",
            "passed": passed,
            "details": f"{out_of_range:,} out of range [{min_val}, {max_val}]"
        })
        return passed
    
    def check_accepted_values(self, table_name: str, column: str, accepted: list) -> bool:
        """Check column values are in accepted list"""
        df = self.read_table(table_name)
        
        invalid_count = df.filter(
            ~col(column).isin(accepted) & col(column).isNotNull()
        ).count()
        
        passed = invalid_count == 0
        
        self.results.append({
            "table": table_name,
            "check": f"accepted({column})",
            "passed": passed,
            "details": f"{invalid_count:,} invalid values"
        })
        return passed
    
    def print_results(self):
        """Print validation results"""
        print("\n" + "=" * 70)
        print("DATA QUALITY REPORT (PySpark)")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Bronze Path: {self.bronze_path}")
        print()
        
        passed = sum(1 for r in self.results if r["passed"])
        failed = len(self.results) - passed
        
        for r in self.results:
            status = "✓" if r["passed"] else "✗"
            print(f"  {status} [{r['table']}] {r['check']}: {r['details']}")
        
        print()
        print("-" * 70)
        print(f"SUMMARY: {passed} passed, {failed} failed")
        
        if failed > 0:
            print("⚠️  Some quality checks failed!")
        else:
            print("✅ All quality checks passed!")
        
        return failed == 0


def run_quality_checks():
    """Run all quality checks"""
    spark = create_spark_session()
    checker = SparkDataQualityChecker(spark, BRONZE_PATH)
    
    # Table existence
    for table in ["suppliers", "products", "locations", "carriers",
                  "sales", "inventory", "purchase_orders", "shipments"]:
        checker.check_table_exists(table)
    
    # Row counts
    checker.check_row_count("suppliers", min_rows=20)
    checker.check_row_count("products", min_rows=100)
    checker.check_row_count("sales", min_rows=1000000)
    checker.check_row_count("inventory", min_rows=100000)
    
    # Uniqueness
    checker.check_unique("suppliers", "supplier_id")
    checker.check_unique("products", "sku")
    checker.check_unique("locations", "location_id")
    checker.check_unique("carriers", "carrier_id")
    
    # Null checks
    checker.check_null_percentage("products", "sku", max_pct=0.0)
    checker.check_null_percentage("products", "unit_cost", max_pct=0.0)
    checker.check_null_percentage("sales", "revenue", max_pct=0.05)
    checker.check_null_percentage("inventory", "on_hand_qty", max_pct=0.10)
    
    # Referential integrity
    checker.check_referential_integrity("sales", "sku", "products", "sku")
    checker.check_referential_integrity("sales", "store_id", "locations", "location_id")
    checker.check_referential_integrity("inventory", "sku", "products", "sku")
    
    # Value ranges
    checker.check_value_range("products", "unit_cost", min_val=0)
    checker.check_value_range("products", "unit_price", min_val=0)
    checker.check_value_range("sales", "units_sold", min_val=0)
    checker.check_value_range("inventory", "on_hand_qty", min_val=0)
    
    # Accepted values
    checker.check_accepted_values("products", "abc_class", ["A", "B", "C"])
    checker.check_accepted_values("locations", "location_type", ["PLANT", "DC", "STORE"])
    
    success = checker.print_results()
    spark.stop()
    
    return success


if __name__ == "__main__":
    success = run_quality_checks()
    exit(0 if success else 1)
