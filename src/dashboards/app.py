"""
Phase 5: Quantum Bricks Supply Chain Analytics Dashboard
Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Quantum Bricks Analytics",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #2d5a87;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📦 Quantum Bricks</p>', unsafe_allow_html=True)
st.markdown("### Supply Chain Analytics Platform")
st.markdown("---")

# Navigation cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="metric-card">
        <h3>📊 Executive Dashboard</h3>
        <p>Revenue trends, forecast accuracy, and key business KPIs</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <h3>🔍 Operations</h3>
        <p>SKU/store drilldowns, anomaly analysis, inventory health</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <h3>🤖 MLOps Monitor</h3>
        <p>Model performance, drift detection, retraining status</p>
    </div>
    """, unsafe_allow_html=True)

st.info("👈 **Use the sidebar to navigate between dashboards**")

st.markdown("---")

# Quick status
st.subheader("System Status")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Data Pipeline", "✅ Healthy")
s2.metric("Models", "✅ Production")
s3.metric("Drift Status", "⚠️ Monitor")
s4.metric("Last Refresh", "Live")

st.markdown("---")
st.caption("Quantum Bricks © 2024 | Phase 5: BI Dashboards")