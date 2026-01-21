"""
Data Quality Checks using DuckDB
Validates local Bronze layer (Delta Lake).
"""
import duckdb
from pathlib import Path
from datetime import datetime

BRONZE_PATH = Path("C:/Users/Manu/supply_chain_project/data/bronze")


class DataQualityChecker:
    def __init__(self, bronze_path: Path):
        self.bronze_path = bronze_path
        self.con = duckdb.connect()
        self.results = []
    
    def get_table_path(self, table_name: str) -> str:
        return str(self.bronze_path / table_name)
    
    def check_table_exists(self, table_name: str) -> bool:
        path = self.bronze_path / table_name
        exists = path.exists() and path.is_dir()
        self.results.append({
            "table": table_name,
            "check": "exists",
            "passed": exists,
            "details": "Delta table" if exists else "NOT FOUND"
        })
        return exists
    
    def check_row_count(self, table_name: str, min_rows: int = 1) -> bool:
        path = self.get_table_path(table_name)
        count = self.con.execute(f"SELECT COUNT(*) FROM delta_scan('{path}')").fetchone()[0]
        
        passed = count >= min_rows
        self.results.append({
            "table": table_name,
            "check": "row_count",
            "passed": passed,
            "details": f"{count:,} rows (min: {min_rows:,})"
        })
        return passed
    
    def check_null_percentage(self, table_name: str, column: str, max_pct: float = 0.1) -> bool:
        path = self.get_table_path(table_name)
        result = self.con.execute(f"""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS nulls
            FROM delta_scan('{path}')
        """).fetchone()
        
        total, nulls = result
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
        path = self.get_table_path(table_name)
        result = self.con.execute(f"""
            SELECT 
                COUNT(*) AS total,
                COUNT(DISTINCT {column}) AS unique_count
            FROM delta_scan('{path}')
        """).fetchone()
        
        total, unique = result
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
        path = self.get_table_path(table_name)
        ref_path = self.get_table_path(ref_table)
        
        result = self.con.execute(f"""
            SELECT COUNT(*) 
            FROM delta_scan('{path}') t
            LEFT JOIN delta_scan('{ref_path}') r ON t.{column} = r.{ref_column}
            WHERE r.{ref_column} IS NULL AND t.{column} IS NOT NULL
        """).fetchone()[0]
        
        passed = result == 0
        
        self.results.append({
            "table": table_name,
            "check": f"ref({column}→{ref_table}.{ref_column})",
            "passed": passed,
            "details": f"{result:,} orphan records"
        })
        return passed
    
    def check_value_range(self, table_name: str, column: str, 
                          min_val: float = None, max_val: float = None) -> bool:
        path = self.get_table_path(table_name)
        
        conditions = []
        if min_val is not None:
            conditions.append(f"{column} < {min_val}")
        if max_val is not None:
            conditions.append(f"{column} > {max_val}")
        
        where_clause = " OR ".join(conditions)
        
        result = self.con.execute(f"""
            SELECT COUNT(*) FROM delta_scan('{path}') WHERE {where_clause}
        """).fetchone()[0]
        
        passed = result == 0
        
        self.results.append({
            "table": table_name,
            "check": f"range({column})",
            "passed": passed,
            "details": f"{result:,} out of range [{min_val}, {max_val}]"
        })
        return passed
    
    def check_accepted_values(self, table_name: str, column: str, accepted: list) -> bool:
        path = self.get_table_path(table_name)
        accepted_str = ", ".join([f"'{v}'" for v in accepted])
        
        result = self.con.execute(f"""
            SELECT COUNT(*) FROM delta_scan('{path}')
            WHERE {column} NOT IN ({accepted_str}) AND {column} IS NOT NULL
        """).fetchone()[0]
        
        passed = result == 0
        
        self.results.append({
            "table": table_name,
            "check": f"accepted({column})",
            "passed": passed,
            "details": f"{result:,} invalid values"
        })
        return passed
    
    def print_results(self):
        print("\n" + "=" * 70)
        print("DATA QUALITY REPORT")
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
    checker = DataQualityChecker(BRONZE_PATH)
    
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
    checker.check_null_percentage("inventory", "on_hand_qty", max_pct=0.05)
    
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
    
    return checker.print_results()


if __name__ == "__main__":
    success = run_quality_checks()
    exit(0 if success else 1)