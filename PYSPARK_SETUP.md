# PySpark Setup Guide (Windows)

## Prerequisites

### 1. Install Java (Required for Spark)

```powershell
# Option A: Download from Oracle
# https://www.oracle.com/java/technologies/downloads/#java11

# Option B: Use Chocolatey
choco install openjdk11

# Verify
java -version
```

Set JAVA_HOME:
```powershell
# Add to System Environment Variables
JAVA_HOME = C:\Program Files\Java\jdk-11
Path += %JAVA_HOME%\bin
```

### 2. Install PySpark

```bash
pip install pyspark==3.5.0 delta-spark==3.0.0
```

### 3. Verify Installation

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Test") \
    .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
    .getOrCreate()

print(f"Spark version: {spark.version}")
spark.stop()
```

---

## Project Structure

```
supply_chain_project/
├── src/
│   ├── ingestion/
│   │   └── load_bronze.py           # Pandas version
│   ├── quality/
│   │   └── validate_bronze.py       # DuckDB version
│   └── spark/                       # NEW - PySpark versions
│       ├── load_bronze_spark.py
│       ├── validate_bronze_spark.py
│       ├── transform_silver_spark.py
│       ├── transform_gold_spark.py
│       └── run_spark_pipeline.py
├── data/
│   ├── bronze/          # Pandas + Delta Lake
│   ├── bronze_spark/    # PySpark + Delta Lake
│   ├── silver_spark/    # PySpark Silver
│   └── gold_spark/      # PySpark Gold
```

---

## Running the PySpark Pipeline

### Full Pipeline
```bash
cd C:\Users\Manu\supply_chain_project
python src/spark/run_spark_pipeline.py
```

### Individual Steps
```bash
# Bronze only
python src/spark/load_bronze_spark.py

# Validate Bronze
python src/spark/validate_bronze_spark.py

# Silver only
python src/spark/transform_silver_spark.py

# Gold only
python src/spark/transform_gold_spark.py
```

### Skip Bronze (use existing data)
```bash
python src/spark/run_spark_pipeline.py --skip-bronze
```

---

## Output Locations

| Layer | Pandas/dbt Version | PySpark Version |
|-------|-------------------|-----------------|
| Bronze | `data/bronze/` | `data/bronze_spark/` |
| Silver | `data/warehouse.duckdb` | `data/silver_spark/` |
| Gold | `data/warehouse.duckdb` | `data/gold_spark/` |

---

## Comparing Outputs

Both approaches should produce identical results:

```python
import duckdb

# Compare row counts
pandas_count = duckdb.execute("""
    SELECT COUNT(*) FROM delta_scan('data/bronze/sales')
""").fetchone()[0]

spark_count = duckdb.execute("""
    SELECT COUNT(*) FROM delta_scan('data/bronze_spark/sales')
""").fetchone()[0]

print(f"Pandas: {pandas_count:,} rows")
print(f"Spark:  {spark_count:,} rows")
```

---

## Troubleshooting

### "Java not found"
- Ensure JAVA_HOME is set correctly
- Restart terminal after setting environment variables

### "Delta Lake errors"
```bash
# Ensure correct versions
pip install pyspark==3.5.0 delta-spark==3.0.0
```

### "Out of memory"
Edit spark config in scripts:
```python
.config("spark.driver.memory", "8g")  # Increase from 4g
```

### "Slow performance"
Increase parallelism:
```python
.config("spark.sql.shuffle.partitions", "16")  # Default is 8
```

---

## Airflow Integration

Copy the DAG file to your Airflow dags folder:
```bash
cp supply_chain_spark_dag.py C:\Users\Manu\airflow\dags\
```

You'll have two DAGs:
- `supply_chain_etl` - dbt version (6 AM)
- `supply_chain_etl_spark` - PySpark version (7 AM)

---

## Key Differences: Pandas/dbt vs PySpark

| Aspect | Pandas/dbt | PySpark |
|--------|-----------|---------|
| Setup | Simpler | Requires Java |
| Memory | Limited by RAM | Distributed |
| Speed (small data) | Faster | Slower (overhead) |
| Speed (big data) | Slow/OOM | Fast |
| Syntax | SQL (dbt) | Python API |
| Scalability | Single machine | Cluster-ready |
| Industry use | Analytics teams | Data engineering |

---

## Interview Talking Points

> "I implemented the same ETL pipeline using both dbt and PySpark to demonstrate proficiency in both tools. For smaller datasets, dbt with DuckDB is faster due to lower overhead. For larger datasets or production environments requiring horizontal scaling, the PySpark implementation can be deployed on Databricks or EMR with minimal changes."
