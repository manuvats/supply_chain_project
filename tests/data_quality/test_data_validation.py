"""
Tests for data validation helper functions.
Verifies validation logic works correctly (not actual data).
Actual data validation is handled by validate_bronze.py and dbt tests.
"""
import pytest
import pandas as pd
import numpy as np


class TestValidationHelpers:
    """Tests for validation utility functions."""

    def test_null_check_function(self):
        """Test null detection logic."""
        def check_nulls(df, columns):
            return {col: df[col].isna().sum() for col in columns}
        
        df = pd.DataFrame({
            "a": [1, 2, None],
            "b": [1, None, None],
        })
        
        result = check_nulls(df, ["a", "b"])
        assert result["a"] == 1
        assert result["b"] == 2

    def test_range_validation_function(self):
        """Test value range validation logic."""
        def validate_range(series, min_val, max_val):
            return ((series >= min_val) & (series <= max_val)).all()
        
        valid = pd.Series([10, 20, 30])
        invalid = pd.Series([10, 20, 100])
        
        assert validate_range(valid, 0, 50) is True
        assert validate_range(invalid, 0, 50) is False

    def test_duplicate_detection_function(self):
        """Test duplicate detection logic."""
        def find_duplicates(df, columns):
            return df.duplicated(subset=columns, keep=False).sum()
        
        df = pd.DataFrame({
            "id": [1, 2, 2, 3],
            "value": [10, 20, 20, 30],
        })
        
        assert find_duplicates(df, ["id"]) == 2
        assert find_duplicates(df, ["id", "value"]) == 2

    def test_date_gap_detection(self):
        """Test date continuity check logic."""
        def find_date_gaps(dates, expected_freq="D"):
            dates = pd.to_datetime(dates).sort_values()
            gaps = dates.diff().dropna()
            expected = pd.Timedelta(1, expected_freq)
            return (gaps > expected).sum()
        
        continuous = pd.Series(["2023-01-01", "2023-01-02", "2023-01-03"])
        with_gap = pd.Series(["2023-01-01", "2023-01-02", "2023-01-05"])
        
        assert find_date_gaps(continuous) == 0
        assert find_date_gaps(with_gap) == 1

    def test_zscore_outlier_detection(self):
        """Test z-score outlier detection logic."""
        def detect_zscore_outliers(series, threshold=3):
            z = (series - series.mean()) / series.std()
            return (z.abs() > threshold).sum()
        
        normal = pd.Series([10, 11, 10, 12, 11, 10])
        with_outlier = pd.Series([10, 11, 10, 12, 11, 100])
        
        assert detect_zscore_outliers(normal) == 0
        assert detect_zscore_outliers(with_outlier) >= 1

    def test_iqr_outlier_detection(self):
        """Test IQR outlier detection logic."""
        def detect_iqr_outliers(series, multiplier=1.5):
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
            return ((series < lower) | (series > upper)).sum()
        
        normal = pd.Series([10, 11, 10, 12, 11, 10])
        with_outlier = pd.Series([10, 11, 10, 12, 11, 100])
        
        assert detect_iqr_outliers(normal) == 0
        assert detect_iqr_outliers(with_outlier) >= 1

    def test_completeness_ratio(self):
        """Test completeness calculation logic."""
        def calc_completeness(df):
            return 1 - (df.isna().sum().sum() / df.size)
        
        complete = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        partial = pd.DataFrame({"a": [1, None], "b": [3, None]})
        
        assert calc_completeness(complete) == 1.0
        assert calc_completeness(partial) == 0.5
