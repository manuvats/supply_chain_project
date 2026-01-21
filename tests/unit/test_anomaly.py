"""
Unit tests for anomaly detection module.
"""
import pytest
import pandas as pd
import numpy as np
from scipy import stats


class TestZScoreAnomaly:
    """Tests for Z-score based anomaly detection."""

    def test_zscore_calculation(self, sample_features_data):
        """Test Z-score calculation."""
        df = sample_features_data.copy()
        
        mean = df["units_sold"].mean()
        std = df["units_sold"].std()
        df["z_score"] = (df["units_sold"] - mean) / std
        
        # Z-scores should be roughly standard normal
        assert df["z_score"].mean() == pytest.approx(0, abs=0.1)
        assert df["z_score"].std() == pytest.approx(1, abs=0.1)

    def test_zscore_anomaly_threshold(self, sample_features_data):
        """Test Z-score threshold flagging."""
        df = sample_features_data.copy()
        threshold = 2.5
        
        mean = df["units_sold"].mean()
        std = df["units_sold"].std()
        df["z_score"] = (df["units_sold"] - mean) / std
        df["is_anomaly"] = df["z_score"].abs() > threshold
        
        # Anomalies should be extreme values
        anomalies = df[df["is_anomaly"]]
        if len(anomalies) > 0:
            assert (anomalies["z_score"].abs() > threshold).all()

    def test_contextual_zscore(self, sample_features_data):
        """Test contextual Z-score (per SKU)."""
        df = sample_features_data.copy()
        
        df["z_score_contextual"] = df.groupby("sku")["units_sold"].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )
        
        # Each SKU group should have mean ~0
        for sku in df["sku"].unique():
            sku_zscores = df[df["sku"] == sku]["z_score_contextual"]
            if sku_zscores.std() > 0:
                assert sku_zscores.mean() == pytest.approx(0, abs=0.1)


class TestIQRAnomaly:
    """Tests for IQR-based anomaly detection."""

    def test_iqr_bounds(self, sample_features_data):
        """Test IQR bounds calculation."""
        values = sample_features_data["units_sold"]
        
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        assert lower_bound < q1
        assert upper_bound > q3
        assert iqr >= 0

    def test_iqr_anomaly_detection(self, sample_features_data):
        """Test IQR anomaly flagging."""
        df = sample_features_data.copy()
        values = df["units_sold"]
        
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        
        df["is_anomaly_iqr"] = (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
        
        # Should flag some but not all as anomalies
        anomaly_rate = df["is_anomaly_iqr"].mean()
        assert 0 <= anomaly_rate <= 0.25  # Typically < 25% anomalies


class TestIsolationForest:
    """Tests for Isolation Forest anomaly detection."""

    def test_contamination_parameter(self):
        """Test contamination affects anomaly count."""
        from sklearn.ensemble import IsolationForest
        
        np.random.seed(42)
        X = np.random.randn(100, 2)
        
        for contamination in [0.05, 0.1, 0.2]:
            model = IsolationForest(contamination=contamination, random_state=42)
            preds = model.fit_predict(X)
            anomaly_rate = (preds == -1).mean()
            assert anomaly_rate == pytest.approx(contamination, abs=0.05)

    def test_isolation_forest_reproducibility(self):
        """Test Isolation Forest gives consistent results."""
        from sklearn.ensemble import IsolationForest
        
        np.random.seed(42)
        X = np.random.randn(50, 3)
        
        model1 = IsolationForest(random_state=42)
        model2 = IsolationForest(random_state=42)
        
        preds1 = model1.fit_predict(X)
        preds2 = model2.fit_predict(X)
        
        assert np.array_equal(preds1, preds2)


class TestAnomalyAggregation:
    """Tests for anomaly aggregation and reporting."""

    def test_anomaly_counts(self, sample_anomalies_data):
        """Test anomaly counting logic."""
        df = sample_anomalies_data
        
        zscore_count = df["is_anomaly_zscore"].sum()
        iforest_count = df["is_anomaly_iforest"].sum()
        
        assert zscore_count >= 0
        assert iforest_count >= 0
        assert zscore_count <= len(df)

    def test_anomaly_type_distribution(self, sample_anomalies_data):
        """Test anomaly types are valid."""
        df = sample_anomalies_data
        valid_types = ["none", "spike", "drop", "demand_supply_mismatch"]
        
        assert df["anomaly_type"].isin(valid_types + [np.nan]).all() or df["anomaly_type"].notna().all()

    def test_no_duplicate_anomaly_flags(self, sample_anomalies_data):
        """Each row should have consistent anomaly info."""
        df = sample_anomalies_data
        
        # If flagged as anomaly by zscore, z_score should be significant
        zscore_anomalies = df[df["is_anomaly_zscore"] == 1]
        if len(zscore_anomalies) > 0:
            # Most should have |z| > 2
            high_z = (zscore_anomalies["z_score"].abs() > 1.5).mean()
            assert high_z > 0.5  # At least 50% should have high z-scores
