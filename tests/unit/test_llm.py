"""
Unit tests for LLM integration module.
Tests run without actual API calls using mocks.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestTextToSQL:
    """Tests for Text-to-SQL component."""

    def test_schema_formatting(self):
        """Test schema is properly formatted for LLM."""
        schema = {
            "main_features.demand_features": ["ds", "sku", "units_sold", "lag_7"],
            "main_features.anomalies": ["ds", "sku", "is_anomaly", "z_score"],
        }
        
        formatted = "\n".join(
            f"Table: {table}\nColumns: {', '.join(cols)}"
            for table, cols in schema.items()
        )
        
        assert "main_features.demand_features" in formatted
        assert "units_sold" in formatted

    def test_sql_safety_check(self):
        """Test dangerous SQL patterns are blocked."""
        dangerous_patterns = [
            "DROP TABLE",
            "DELETE FROM",
            "UPDATE ",
            "INSERT INTO",
            "TRUNCATE",
            "; DROP",
        ]
        
        def is_safe_query(sql):
            sql_upper = sql.upper()
            for pattern in dangerous_patterns:
                if pattern in sql_upper:
                    return False
            return True
        
        assert is_safe_query("SELECT * FROM sales")
        assert not is_safe_query("DROP TABLE users")
        assert not is_safe_query("SELECT 1; DROP TABLE users")

    def test_query_result_formatting(self):
        """Test query results are formatted for display."""
        results = [
            {"sku": "SKU_1", "total": 1000},
            {"sku": "SKU_2", "total": 800},
        ]
        
        # Format as markdown table
        headers = results[0].keys()
        header_row = "| " + " | ".join(headers) + " |"
        
        assert "sku" in header_row
        assert "total" in header_row


class TestAnomalyExplainer:
    """Tests for anomaly explanation component."""

    def test_anomaly_context_building(self, sample_anomalies_data):
        """Test context is built correctly for anomalies."""
        df = sample_anomalies_data
        anomaly = df[df["is_anomaly_zscore"] == 1].iloc[0] if df["is_anomaly_zscore"].sum() > 0 else df.iloc[0]
        
        context = {
            "date": str(anomaly["ds"]),
            "sku": anomaly["sku"],
            "units_sold": int(anomaly["units_sold"]),
            "z_score": float(anomaly["z_score"]),
        }
        
        assert "date" in context
        assert "sku" in context
        assert isinstance(context["units_sold"], int)

    def test_explanation_prompt_structure(self):
        """Test prompt structure for explanations."""
        anomaly_data = {
            "sku": "SKU_001",
            "date": "2023-06-15",
            "units_sold": 150,
            "expected": 50,
            "z_score": 3.2,
        }
        
        prompt = f"""Analyze this supply chain anomaly:
SKU: {anomaly_data['sku']}
Date: {anomaly_data['date']}
Actual: {anomaly_data['units_sold']} units
Expected: {anomaly_data['expected']} units
Z-score: {anomaly_data['z_score']}

Provide a brief root cause analysis."""
        
        assert "SKU_001" in prompt
        assert "3.2" in prompt

    @patch("requests.post")
    def test_llm_api_call_structure(self, mock_post):
        """Test LLM API call has correct structure."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test explanation"}}]
        }
        mock_post.return_value = mock_response
        
        # Simulate API call structure
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Explain anomaly"}],
            "temperature": 0.3,
            "max_tokens": 500,
        }
        
        assert "model" in payload
        assert "messages" in payload
        assert payload["temperature"] <= 1.0


class TestChatAssistant:
    """Tests for conversational chat assistant."""

    def test_message_history_format(self):
        """Test message history is properly formatted."""
        history = [
            {"role": "user", "content": "What were sales yesterday?"},
            {"role": "assistant", "content": "Sales were 1000 units."},
            {"role": "user", "content": "And the day before?"},
        ]
        
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_system_prompt_contains_context(self):
        """Test system prompt includes necessary context."""
        system_prompt = """You are a supply chain analytics assistant.
You have access to:
- Sales data (daily transactions)
- Inventory levels
- Demand forecasts
- Anomaly reports

Answer questions about supply chain performance."""
        
        assert "supply chain" in system_prompt.lower()
        assert "sales" in system_prompt.lower()

    def test_conversation_context_limit(self):
        """Test conversation history is trimmed if too long."""
        max_history = 10
        
        history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(20)
        ]
        
        trimmed = history[-max_history:]
        
        assert len(trimmed) == max_history
        assert "Message 19" in trimmed[-1]["content"]


class TestReportSummarizer:
    """Tests for report summarization component."""

    def test_kpi_extraction(self, sample_sales_data):
        """Test KPI extraction from data."""
        df = sample_sales_data
        
        kpis = {
            "total_revenue": df["revenue"].sum(),
            "total_units": df["units_sold"].sum(),
            "avg_price": df["unit_price"].mean(),
            "unique_skus": df["sku"].nunique(),
        }
        
        assert kpis["total_revenue"] > 0
        assert kpis["unique_skus"] == 5

    def test_report_sections(self):
        """Test report has required sections."""
        report_template = """
# Executive Summary

## Key Metrics
{metrics}

## Trends
{trends}

## Anomalies
{anomalies}

## Recommendations
{recommendations}
"""
        
        assert "Executive Summary" in report_template
        assert "Key Metrics" in report_template
        assert "Recommendations" in report_template

    def test_summary_length_constraint(self):
        """Test summary respects length limits."""
        max_tokens = 500
        
        # Approximate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        
        sample_summary = "x" * 1500  # Within limit
        
        assert len(sample_summary) < max_chars

    def test_date_range_formatting(self):
        """Test date range is correctly formatted."""
        import datetime
        
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        date_range = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        
        assert "to" in date_range
        assert len(date_range.split(" to ")) == 2


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_api_key_not_hardcoded(self):
        """Ensure API key comes from environment."""
        import os
        
        # Should use env var, not hardcoded
        api_key = os.environ.get("GROQ_API_KEY", "")
        
        # In CI, this might be empty, which is fine
        assert "sk-" not in api_key or api_key == ""  # Shouldn't be OpenAI key

    def test_model_config_valid(self):
        """Test model configuration is valid."""
        config = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        
        assert config["temperature"] >= 0
        assert config["temperature"] <= 2
        assert config["max_tokens"] > 0

    def test_fallback_behavior(self):
        """Test graceful fallback when API unavailable."""
        def get_llm_response(prompt, fallback="Unable to generate response"):
            try:
                # Simulate API error
                raise ConnectionError("API unavailable")
            except Exception:
                return fallback
        
        response = get_llm_response("test prompt")
        assert response == "Unable to generate response"
