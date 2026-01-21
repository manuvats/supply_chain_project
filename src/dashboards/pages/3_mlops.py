"""
Page 3: MLOps Monitor Dashboard
Model performance, drift detection, retraining status
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import json

st.set_page_config(page_title="MLOps Monitor", page_icon="🤖", layout="wide")

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
MLFLOW_PATH = PROJECT_ROOT / "mlruns"
DRIFT_REPORT_PATH = PROJECT_ROOT / "outputs" / "drift_report.json"
MODEL_COMPARISON_PATH = PROJECT_ROOT / "outputs" / "model_comparison_results.csv"

@st.cache_data(ttl=600)
def load_drift_report():
    if DRIFT_REPORT_PATH.exists():
        with open(DRIFT_REPORT_PATH) as f:
            return json.load(f)
    return None

@st.cache_data(ttl=600)
def load_model_comparison():
    if MODEL_COMPARISON_PATH.exists():
        return pd.read_csv(MODEL_COMPARISON_PATH)
    return pd.DataFrame()

drift_report = load_drift_report()
comparison_df = load_model_comparison()

# Header
st.markdown("# 🤖 MLOps Monitor")
st.markdown("Model lifecycle, drift detection, and retraining triggers")
st.markdown("---")

# Status
s1, s2, s3, s4 = st.columns(4)
s1.metric("Models Tracked", "✅ Active" if not comparison_df.empty else "N/A")
if not comparison_df.empty and 'mape' in comparison_df.columns:
    s2.metric("Best MAPE", f"{comparison_df['mape'].min():.1%}")
else:
    s2.metric("Best MAPE", "N/A")

if drift_report:
    drift_detected = drift_report.get('drift_detected', False)
    s3.metric("Drift Status", "⚠️ Drift" if drift_detected else "✅ Stable")
    s4.metric("Features Drifted", drift_report.get('drifted_features_count', 0))
else:
    s3.metric("Drift Status", "⏳ Not Checked")
    s4.metric("Features Drifted", "N/A")

st.markdown("---")

# Tabs
tab1, tab2, tab3 = st.tabs(["📈 Model Performance", "🔄 Drift Analysis", "🏭 Registry"])

with tab1:
    st.subheader("Model Comparison")
    if not comparison_df.empty:
        agg_df = comparison_df[comparison_df['segment'] == 'all_items'] if 'segment' in comparison_df.columns else comparison_df
        
        col1, col2 = st.columns(2)
        with col1:
            if 'model' in agg_df.columns and 'wape' in agg_df.columns:
                fig = px.bar(agg_df.sort_values('wape'), x='model', y='wape', color='wape', color_continuous_scale='RdYlGn_r')
                fig.update_layout(xaxis_title="Model", yaxis_title="WAPE", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.dataframe(agg_df, use_container_width=True)
    else:
        st.info("Run model comparison (Phase 2.3) first.")

with tab2:
    st.subheader("Data Drift Analysis")
    if drift_report:
        col1, col2 = st.columns([1, 2])
        with col1:
            status = "🔴 Drift Detected" if drift_report.get('drift_detected', False) else "🟢 No Drift"
            st.markdown(f"**Status**: {status}")
            st.markdown(f"**Report Date**: {drift_report.get('report_date', 'N/A')}")
        
        with col2:
            feature_drift = drift_report.get('feature_drift', {})
            if feature_drift:
                drift_df = pd.DataFrame([
                    {'feature': k, 'p_value': v.get('p_value', 0), 'drifted': v.get('drifted', False)}
                    for k, v in feature_drift.items()
                ])
                fig = px.bar(drift_df.sort_values('p_value'), x='feature', y='p_value',
                             color='drifted', color_discrete_map={True: '#ef4444', False: '#10b981'})
                fig.add_hline(y=0.05, line_dash="dash", line_color="orange")
                st.plotly_chart(fig, use_container_width=True)
        
        if drift_report.get('drift_detected', False):
            st.warning("**Action Required**: Consider retraining models.")
    else:
        st.info("Run drift monitoring (Phase 3.3) to generate report.")

with tab3:
    st.subheader("Model Registry & Deployment")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Quick Commands")
        st.code("""
# Register best model
python src/mlops/model_registry.py register

# Promote to production  
python src/mlops/model_registry.py promote --stage production

# Start API server
uvicorn src.mlops.serve_model:app --port 8000
        """)
    
    with col2:
        st.markdown("#### Retraining Triggers")
        if st.button("🔄 Trigger Retraining", type="primary"):
            st.info("Run: `airflow dags trigger retrain_demand_model`")
        if st.button("📊 Generate Drift Report"):
            st.info("Run: `python src/mlops/drift_monitor.py`")

st.markdown("---")
st.caption("MLOps data from MLflow & Evidently | Quantum Bricks Analytics")
