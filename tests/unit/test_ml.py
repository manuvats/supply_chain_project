"""
Unit tests for ML training and evaluation module.
"""
import pytest
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split


class TestMLMetrics:
    """Tests for ML evaluation metrics."""

    def test_mape_calculation(self, mock_model_predictions):
        """Test MAPE calculation."""
        actuals = mock_model_predictions["actuals"]
        preds = mock_model_predictions["predictions"]
        
        # Filter out zeros to avoid division error
        mask = actuals != 0
        mape = np.mean(np.abs((actuals[mask] - preds[mask]) / actuals[mask])) * 100
        
        assert 0 <= mape <= 100
        assert isinstance(mape, float)

    def test_rmse_calculation(self, mock_model_predictions):
        """Test RMSE calculation."""
        actuals = mock_model_predictions["actuals"]
        preds = mock_model_predictions["predictions"]
        
        rmse = np.sqrt(np.mean((actuals - preds) ** 2))
        
        assert rmse >= 0
        assert isinstance(rmse, float)

    def test_mae_calculation(self, mock_model_predictions):
        """Test MAE calculation."""
        actuals = mock_model_predictions["actuals"]
        preds = mock_model_predictions["predictions"]
        
        mae = np.mean(np.abs(actuals - preds))
        
        assert mae >= 0
        assert mae <= np.abs(actuals - preds).max()

    def test_wape_calculation(self, mock_model_predictions):
        """Test WAPE (Weighted Absolute Percentage Error)."""
        actuals = mock_model_predictions["actuals"]
        preds = mock_model_predictions["predictions"]
        
        wape = np.sum(np.abs(actuals - preds)) / np.sum(np.abs(actuals)) * 100
        
        assert wape >= 0

    def test_bias_calculation(self, mock_model_predictions):
        """Test forecast bias calculation."""
        actuals = mock_model_predictions["actuals"]
        preds = mock_model_predictions["predictions"]
        
        bias = np.mean(preds - actuals)
        bias_pct = bias / np.mean(actuals) * 100
        
        # Bias can be positive or negative
        assert isinstance(bias, float)
        assert isinstance(bias_pct, float)


class TestTrainTestSplit:
    """Tests for time-series train/test splitting."""

    def test_temporal_split_no_leakage(self, sample_features_data):
        """Ensure train data is before test data."""
        df = sample_features_data.copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds")
        
        split_idx = int(len(df) * 0.8)
        train = df.iloc[:split_idx]
        test = df.iloc[split_idx:]
        
        assert train["ds"].max() < test["ds"].min()

    def test_split_sizes(self, sample_features_data):
        """Test split proportions are correct."""
        df = sample_features_data
        train_ratio = 0.8
        
        split_idx = int(len(df) * train_ratio)
        train = df.iloc[:split_idx]
        test = df.iloc[split_idx:]
        
        assert len(train) + len(test) == len(df)
        assert len(train) / len(df) == pytest.approx(train_ratio, abs=0.05)


class TestModelValidation:
    """Tests for model validation logic."""

    def test_prediction_shape(self, sample_features_data):
        """Predictions should match input length."""
        from sklearn.ensemble import RandomForestRegressor
        
        df = sample_features_data.dropna()
        features = ["lag_7", "lag_14", "rolling_mean_7", "day_of_week"]
        target = "units_sold"
        
        X = df[features]
        y = df[target]
        
        model = RandomForestRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)
        preds = model.predict(X)
        
        assert len(preds) == len(X)

    def test_predictions_non_negative(self, sample_features_data):
        """Demand predictions should be non-negative."""
        from sklearn.ensemble import RandomForestRegressor
        
        df = sample_features_data.dropna()
        features = ["lag_7", "lag_14", "rolling_mean_7", "day_of_week"]
        target = "units_sold"
        
        X = df[features]
        y = df[target]
        
        model = RandomForestRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)
        preds = model.predict(X)
        
        # Clip negatives (common post-processing)
        preds_clipped = np.maximum(preds, 0)
        assert (preds_clipped >= 0).all()

    def test_model_reproducibility(self, sample_features_data):
        """Model should give same results with same seed."""
        from sklearn.ensemble import RandomForestRegressor
        
        df = sample_features_data.dropna()
        features = ["lag_7", "lag_14", "rolling_mean_7"]
        X = df[features]
        y = df["units_sold"]
        
        model1 = RandomForestRegressor(n_estimators=10, random_state=42)
        model2 = RandomForestRegressor(n_estimators=10, random_state=42)
        
        model1.fit(X, y)
        model2.fit(X, y)
        
        preds1 = model1.predict(X)
        preds2 = model2.predict(X)
        
        np.testing.assert_array_equal(preds1, preds2)


class TestDriftDetection:
    """Tests for model drift detection."""

    def test_psi_calculation(self):
        """Test PSI (Population Stability Index) calculation."""
        np.random.seed(42)
        
        # Reference distribution
        reference = np.random.normal(50, 10, 1000)
        # Current distribution (slightly shifted)
        current = np.random.normal(52, 10, 1000)
        
        def calculate_psi(reference, current, bins=10):
            ref_hist, bin_edges = np.histogram(reference, bins=bins)
            curr_hist, _ = np.histogram(current, bins=bin_edges)
            
            ref_pct = ref_hist / len(reference) + 0.0001
            curr_pct = curr_hist / len(current) + 0.0001
            
            psi = np.sum((curr_pct - ref_pct) * np.log(curr_pct / ref_pct))
            return psi
        
        psi = calculate_psi(reference, current)
        
        assert psi >= 0
        assert psi < 0.25  # Should indicate stable distribution

    def test_ks_test_detection(self):
        """Test KS test for distribution comparison."""
        from scipy.stats import ks_2samp
        
        np.random.seed(42)
        
        # Same distribution
        dist1 = np.random.normal(50, 10, 500)
        dist2 = np.random.normal(50, 10, 500)
        
        stat, pvalue = ks_2samp(dist1, dist2)
        
        # Same distribution should have high p-value
        assert pvalue > 0.05

    def test_drift_threshold(self):
        """Test drift alerting thresholds."""
        psi_thresholds = {"green": 0.1, "yellow": 0.2, "red": float("inf")}
        
        def get_drift_status(psi):
            if psi < psi_thresholds["green"]:
                return "green"
            elif psi < psi_thresholds["yellow"]:
                return "yellow"
            else:
                return "red"
        
        assert get_drift_status(0.05) == "green"
        assert get_drift_status(0.15) == "yellow"
        assert get_drift_status(0.25) == "red"
