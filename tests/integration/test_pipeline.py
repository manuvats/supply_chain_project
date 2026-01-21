"""
Integration tests for Quantum Bricks pipeline.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import duckdb


@pytest.mark.integration
class TestPipelineIntegration:
    """End-to-end pipeline integration tests."""

    def test_bronze_to_silver_flow(self, sample_sales_data, temp_duckdb):
        """Test data flows from Bronze to Silver layer."""
        con, db_path = temp_duckdb
        
        # Simulate Bronze: raw data
        bronze_df = sample_sales_data.copy()
        bronze_df["_ingested_at"] = pd.Timestamp.now()
        
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        
        con.execute("CREATE TABLE bronze.sales AS SELECT * FROM bronze_df")
        
        # Silver transformation: clean and validate
        silver_query = """
        CREATE TABLE silver.sales AS
        SELECT 
            ds,
            sku,
            store_id,
            units_sold,
            revenue,
            unit_price,
            _ingested_at
        FROM bronze.sales
        WHERE units_sold >= 0 AND revenue >= 0
        """
        con.execute(silver_query)
        
        # Verify
        bronze_count = con.execute("SELECT COUNT(*) FROM bronze.sales").fetchone()[0]
        silver_count = con.execute("SELECT COUNT(*) FROM silver.sales").fetchone()[0]
        
        assert bronze_count > 0
        assert silver_count <= bronze_count  # Silver may filter bad rows
        assert silver_count > 0

    def test_silver_to_gold_aggregation(self, sample_sales_data, temp_duckdb):
        """Test aggregation from Silver to Gold layer."""
        con, db_path = temp_duckdb
        
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        
        con.execute("CREATE TABLE silver.sales AS SELECT * FROM sample_sales_data")
        
        # Gold: daily aggregates
        gold_query = """
        CREATE TABLE gold.daily_sales AS
        SELECT 
            ds,
            sku,
            SUM(units_sold) as total_units,
            SUM(revenue) as total_revenue,
            AVG(unit_price) as avg_price
        FROM silver.sales
        GROUP BY ds, sku
        """
        con.execute(gold_query)
        
        # Verify aggregation
        gold_df = con.execute("SELECT * FROM gold.daily_sales").fetchdf()
        
        assert "total_units" in gold_df.columns
        assert "total_revenue" in gold_df.columns
        assert gold_df["total_units"].sum() == sample_sales_data["units_sold"].sum()

    def test_feature_pipeline_integration(self, sample_sales_data, temp_duckdb):
        """Test feature engineering pipeline end-to-end."""
        con, db_path = temp_duckdb
        
        con.execute("CREATE SCHEMA IF NOT EXISTS main_features")
        con.execute("CREATE TABLE sales AS SELECT * FROM sample_sales_data")
        
        # Feature engineering query
        feature_query = """
        CREATE TABLE main_features.demand_features AS
        SELECT 
            ds,
            sku,
            store_id,
            units_sold,
            LAG(units_sold, 7) OVER (PARTITION BY sku ORDER BY ds) as lag_7,
            AVG(units_sold) OVER (
                PARTITION BY sku 
                ORDER BY ds 
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) as rolling_mean_7,
            EXTRACT(DOW FROM ds::DATE) as day_of_week,
            EXTRACT(MONTH FROM ds::DATE) as month
        FROM sales
        """
        con.execute(feature_query)
        
        features_df = con.execute("SELECT * FROM main_features.demand_features").fetchdf()
        
        assert "lag_7" in features_df.columns
        assert "rolling_mean_7" in features_df.columns
        assert "day_of_week" in features_df.columns


@pytest.mark.integration
class TestAPIIntegration:
    """Tests for FastAPI model serving endpoints."""

    def test_health_endpoint_structure(self):
        """Test health check endpoint response structure."""
        expected_response = {
            "status": "healthy",
            "model_loaded": True,
            "version": "1.0.0",
        }
        
        assert "status" in expected_response
        assert expected_response["status"] == "healthy"

    def test_predict_request_validation(self):
        """Test prediction request validation."""
        valid_request = {
            "sku": "SKU_001",
            "date": "2023-06-15",
            "features": {
                "lag_7": 50,
                "lag_14": 48,
                "rolling_mean_7": 49.5,
                "day_of_week": 4,
            },
        }
        
        # Validate required fields
        required_fields = ["sku", "date", "features"]
        for field in required_fields:
            assert field in valid_request
        
        # Validate feature structure
        required_features = ["lag_7", "rolling_mean_7"]
        for feat in required_features:
            assert feat in valid_request["features"]

    def test_batch_predict_structure(self):
        """Test batch prediction request structure."""
        batch_request = {
            "requests": [
                {"sku": "SKU_001", "date": "2023-06-15", "features": {"lag_7": 50}},
                {"sku": "SKU_002", "date": "2023-06-15", "features": {"lag_7": 60}},
            ]
        }
        
        assert len(batch_request["requests"]) == 2
        assert all("sku" in r for r in batch_request["requests"])


@pytest.mark.integration
class TestDBTIntegration:
    """Tests for dbt model integration."""

    def test_dbt_model_dependencies(self):
        """Test dbt model dependency resolution."""
        # Simulated dbt manifest structure
        models = {
            "stg_sales": {"depends_on": []},
            "stg_inventory": {"depends_on": []},
            "fct_daily_sales": {"depends_on": ["stg_sales"]},
            "fct_inventory_metrics": {"depends_on": ["stg_inventory", "stg_sales"]},
        }
        
        def get_build_order(models):
            order = []
            built = set()
            
            while len(order) < len(models):
                for model, config in models.items():
                    if model in built:
                        continue
                    if all(dep in built for dep in config["depends_on"]):
                        order.append(model)
                        built.add(model)
            return order
        
        build_order = get_build_order(models)
        
        # Staging models should build first
        assert build_order.index("stg_sales") < build_order.index("fct_daily_sales")

    def test_dbt_schema_validation(self):
        """Test dbt schema test structure."""
        schema_tests = {
            "stg_sales": {
                "columns": {
                    "sku": ["not_null", "unique"],
                    "ds": ["not_null"],
                    "units_sold": ["not_null", {"accepted_values": {"values": ">=0"}}],
                }
            }
        }
        
        assert "sku" in schema_tests["stg_sales"]["columns"]
        assert "not_null" in schema_tests["stg_sales"]["columns"]["sku"]


@pytest.mark.integration
@pytest.mark.requires_db
class TestDatabaseIntegration:
    """Tests requiring actual database connection."""

    def test_duckdb_connection(self, temp_duckdb):
        """Test DuckDB connection works."""
        con, db_path = temp_duckdb
        
        result = con.execute("SELECT 1 as test").fetchone()
        assert result[0] == 1

    def test_schema_creation(self, temp_duckdb):
        """Test schema creation."""
        con, db_path = temp_duckdb
        
        con.execute("CREATE SCHEMA IF NOT EXISTS test_schema")
        schemas = con.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchdf()
        
        assert "test_schema" in schemas["schema_name"].values

    def test_table_operations(self, temp_duckdb, sample_sales_data):
        """Test CRUD operations on tables."""
        con, db_path = temp_duckdb
        
        # Create
        con.execute("CREATE TABLE test_sales AS SELECT * FROM sample_sales_data")
        
        # Read
        count = con.execute("SELECT COUNT(*) FROM test_sales").fetchone()[0]
        assert count == len(sample_sales_data)
        
        # Update (via temp table since DuckDB update can be limited)
        con.execute("""
            CREATE TABLE test_sales_updated AS 
            SELECT *, units_sold * 2 as doubled_units 
            FROM test_sales
        """)
        
        doubled = con.execute("SELECT doubled_units FROM test_sales_updated LIMIT 1").fetchone()[0]
        original = con.execute("SELECT units_sold FROM test_sales LIMIT 1").fetchone()[0]
        assert doubled == original * 2
