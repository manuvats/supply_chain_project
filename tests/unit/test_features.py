"""
Unit tests for feature engineering module.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestDemandFeatures:
    """Tests for demand feature engineering."""

    def test_lag_features_creation(self, sample_sales_data):
        """Test lag feature calculation."""
        df = sample_sales_data.copy()
        df = df.sort_values(["sku", "ds"])
        
        # Create lag features
        df["lag_7"] = df.groupby("sku")["units_sold"].shift(7)
        df["lag_14"] = df.groupby("sku")["units_sold"].shift(14)
        
        assert "lag_7" in df.columns
        assert "lag_14" in df.columns
        # First 7 days should be NaN for lag_7
        assert df.groupby("sku")["lag_7"].apply(lambda x: x.head(7).isna().all()).all()

    def test_rolling_features_creation(self, sample_sales_data):
        """Test rolling statistics calculation."""
        df = sample_sales_data.copy()
        df = df.sort_values(["sku", "ds"])
        
        # Create rolling features
        df["rolling_mean_7"] = df.groupby("sku")["units_sold"].transform(
            lambda x: x.rolling(7, min_periods=1).mean()
        )
        df["rolling_std_7"] = df.groupby("sku")["units_sold"].transform(
            lambda x: x.rolling(7, min_periods=1).std()
        )
        
        assert "rolling_mean_7" in df.columns
        assert "rolling_std_7" in df.columns
        assert df["rolling_mean_7"].notna().any()

    def test_calendar_features(self, sample_sales_data):
        """Test calendar feature extraction."""
        df = sample_sales_data.copy()
        
        df["day_of_week"] = pd.to_datetime(df["ds"]).dt.dayofweek
        df["month"] = pd.to_datetime(df["ds"]).dt.month
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        
        assert df["day_of_week"].between(0, 6).all()
        assert df["month"].between(1, 12).all()
        assert df["is_weekend"].isin([0, 1]).all()

    def test_no_data_leakage(self, sample_sales_data):
        """Ensure features don't leak future data."""
        df = sample_sales_data.copy()
        df = df.sort_values(["sku", "ds"])
        
        # Lag should only use past data
        df["lag_1"] = df.groupby("sku")["units_sold"].shift(1)
        
        for sku in df["sku"].unique():
            sku_data = df[df["sku"] == sku].reset_index(drop=True)
            for i in range(1, len(sku_data)):
                if pd.notna(sku_data.loc[i, "lag_1"]):
                    assert sku_data.loc[i, "lag_1"] == sku_data.loc[i - 1, "units_sold"]

    def test_feature_dtypes(self, sample_features_data):
        """Test feature data types are correct."""
        df = sample_features_data
        
        assert pd.api.types.is_numeric_dtype(df["units_sold"])
        assert pd.api.types.is_numeric_dtype(df["lag_7"])
        assert pd.api.types.is_numeric_dtype(df["rolling_mean_7"])


class TestFeatureValidation:
    """Tests for feature validation logic."""

    def test_no_negative_sales(self, sample_sales_data):
        """Sales should never be negative."""
        assert (sample_sales_data["units_sold"] >= 0).all()

    def test_revenue_consistency(self, sample_sales_data):
        """Revenue should be positive when units sold."""
        df = sample_sales_data
        sold_mask = df["units_sold"] > 0
        assert (df.loc[sold_mask, "revenue"] > 0).all()

    def test_date_continuity(self, sample_sales_data):
        """Check for date gaps per SKU."""
        df = sample_sales_data.copy()
        df["ds"] = pd.to_datetime(df["ds"])
        
        for sku in df["sku"].unique()[:3]:  # Check first 3 SKUs
            sku_dates = df[df["sku"] == sku]["ds"].sort_values()
            date_diffs = sku_dates.diff().dropna()
            # All diffs should be 1 day (no gaps)
            assert (date_diffs == pd.Timedelta(days=1)).all()

    def test_feature_completeness(self, sample_features_data):
        """Check required features exist."""
        required_cols = ["ds", "sku", "units_sold", "lag_7", "rolling_mean_7"]
        for col in required_cols:
            assert col in sample_features_data.columns, f"Missing column: {col}"
