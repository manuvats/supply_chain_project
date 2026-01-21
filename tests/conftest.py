"""
Pytest configuration and shared fixtures for Quantum Bricks tests.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import duckdb

# Project paths - adjust for CI environment
PROJECT_ROOT = Path(__file__).parent.parent
DATA_PATH = PROJECT_ROOT / "data"


@pytest.fixture(scope="session")
def sample_sales_data():
    """Generate sample sales data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    
    data = {
        "ds": np.tile(dates, 5),
        "sku": np.repeat([f"SKU_{i}" for i in range(5)], 100),
        "store_id": np.repeat([f"STORE_{i}" for i in range(5)], 100),
        "units_sold": np.random.poisson(50, 500),
        "revenue": np.random.uniform(100, 1000, 500).round(2),
        "unit_price": np.random.uniform(10, 50, 500).round(2),
    }
    return pd.DataFrame(data)


@pytest.fixture(scope="session")
def sample_features_data():
    """Generate sample feature data for testing."""
    np.random.seed(42)
    n = 200
    
    data = {
        "ds": pd.date_range("2023-01-01", periods=n, freq="D"),
        "sku": [f"SKU_{i % 10}" for i in range(n)],
        "units_sold": np.random.poisson(50, n),
        "lag_7": np.random.poisson(48, n),
        "lag_14": np.random.poisson(52, n),
        "rolling_mean_7": np.random.uniform(45, 55, n),
        "rolling_std_7": np.random.uniform(5, 15, n),
        "day_of_week": [i % 7 for i in range(n)],
        "month": [(i // 30) % 12 + 1 for i in range(n)],
    }
    return pd.DataFrame(data)


@pytest.fixture(scope="session")
def sample_anomalies_data():
    """Generate sample anomaly data for testing."""
    np.random.seed(42)
    n = 50
    
    data = {
        "ds": pd.date_range("2023-01-01", periods=n, freq="D"),
        "sku": [f"SKU_{i % 5}" for i in range(n)],
        "units_sold": np.random.poisson(50, n),
        "z_score": np.random.normal(0, 1, n),
        "is_anomaly_zscore": np.random.choice([0, 1], n, p=[0.9, 0.1]),
        "is_anomaly_iforest": np.random.choice([0, 1], n, p=[0.92, 0.08]),
        "anomaly_type": np.random.choice(["none", "spike", "drop"], n, p=[0.85, 0.1, 0.05]),
    }
    return pd.DataFrame(data)


@pytest.fixture(scope="function")
def temp_duckdb():
    """Create a temporary DuckDB database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name
    
    con = duckdb.connect(db_path)
    yield con, db_path
    
    con.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def mock_model_predictions():
    """Generate mock model predictions for testing."""
    np.random.seed(42)
    n = 100
    
    actuals = np.random.poisson(50, n)
    predictions = actuals + np.random.normal(0, 5, n)
    
    return {
        "actuals": actuals,
        "predictions": predictions,
        "dates": pd.date_range("2023-01-01", periods=n, freq="D"),
    }


# Markers for test categorization
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "requires_db: Tests requiring database")
