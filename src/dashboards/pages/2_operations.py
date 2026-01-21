"""
Page 2: Operations Dashboard
SKU/Store drilldowns, anomaly analysis
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import duckdb

st.set_page_config(page_title="Operations", page_icon="🔍", layout="wide")

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DUCKDB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"

@st.cache_data(ttl=3600)
def load_operational_data():
    """Load detailed operational data."""
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        
        detail_df = conn.execute("""
            SELECT * FROM main_features.demand_features
            ORDER BY ds DESC
            LIMIT 50000
        """).fetchdf()
        
        skus = conn.execute("SELECT DISTINCT sku FROM main_features.demand_features ORDER BY sku").fetchdf()['sku'].tolist()
        stores = conn.execute("SELECT DISTINCT store_id FROM main_features.demand_features ORDER BY store_id").fetchdf()['store_id'].tolist()
        
        conn.close()
        return detail_df, skus, stores
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), [], []

@st.cache_data(ttl=3600)
def load_anomalies():
    """Load anomaly detection results."""
    paths = [
        PROJECT_ROOT / "outputs" / "anomalies_pandas.csv",
        PROJECT_ROOT / "outputs" / "anomaly_summary.csv",
    ]
    for p in paths:
        if p.exists():
            return pd.read_csv(p)
    return pd.DataFrame()

# Load data
detail_df, sku_list, store_list = load_operational_data()
anomaly_df = load_anomalies()

# Header
st.markdown("# 🔍 Operations Dashboard")
st.markdown("SKU-level performance and anomaly detection")
st.markdown("---")

# Filters
st.sidebar.header("Filters")
selected_skus = st.sidebar.multiselect("Select SKUs", options=sku_list[:50], default=sku_list[:3] if sku_list else [])
selected_stores = st.sidebar.multiselect("Select Stores", options=store_list[:20], default=store_list[:2] if store_list else [])

# Apply filters
filtered_df = detail_df.copy()
if selected_skus:
    filtered_df = filtered_df[filtered_df['sku'].isin(selected_skus)]
if selected_stores:
    filtered_df = filtered_df[filtered_df['store_id'].isin(selected_stores)]

# Tabs
tab1, tab2, tab3 = st.tabs(["📦 SKU Analysis", "🏪 Store Analysis", "⚠️ Anomalies"])

with tab1:
    st.subheader("SKU Performance")
    if not filtered_df.empty:
        sku_summary = filtered_df.groupby('sku').agg({
            'units_sold': ['sum', 'mean', 'std'],
            'revenue': 'sum'
        }).round(2)
        sku_summary.columns = ['total_units', 'avg_daily', 'std_dev', 'total_revenue']
        sku_summary = sku_summary.reset_index().sort_values('total_revenue', ascending=False)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("SKUs", len(sku_summary))
        c2.metric("Total Revenue", f"${sku_summary['total_revenue'].sum():,.0f}")
        c3.metric("Avg Daily Units", f"{sku_summary['avg_daily'].mean():.1f}")
        
        if selected_skus and len(selected_skus) <= 5:
            st.markdown("#### Daily Demand by SKU")
            fig = px.line(filtered_df.sort_values('ds'), x='ds', y='units_sold', color='sku')
            fig.update_layout(xaxis_title="", yaxis_title="Units Sold", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(sku_summary.head(20), use_container_width=True)

with tab2:
    st.subheader("Store Performance")
    if not filtered_df.empty:
        store_summary = filtered_df.groupby('store_id').agg({
            'units_sold': 'sum', 'revenue': 'sum', 'sku': 'nunique'
        })
        store_summary.columns = ['total_units', 'total_revenue', 'unique_skus']
        store_summary = store_summary.reset_index().sort_values('total_revenue', ascending=False)
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(store_summary.head(15), x='store_id', y='total_revenue', color='total_revenue', color_continuous_scale='Greens')
            fig.update_layout(xaxis_title="Store", yaxis_title="Revenue ($)", showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.scatter(store_summary, x='total_units', y='total_revenue', size='unique_skus', hover_data=['store_id'])
            fig.update_layout(xaxis_title="Total Units", yaxis_title="Revenue ($)", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("⚠️ Anomaly Detection Results")
    if not anomaly_df.empty:
        anomaly_cols = [c for c in anomaly_df.columns if 'anomaly' in c.lower() or 'outlier' in c.lower()]
        if anomaly_cols:
            total_records = len(anomaly_df)
            cols = st.columns(min(len(anomaly_cols), 4))
            for i, col_name in enumerate(anomaly_cols[:4]):
                count = anomaly_df[col_name].sum() if anomaly_df[col_name].dtype == bool else (anomaly_df[col_name] == 1).sum()
                cols[i].metric(col_name.replace('_', ' ').title(), f"{count:,}", f"{count/total_records*100:.1f}%")
            
            anomaly_df['any_anomaly'] = anomaly_df[anomaly_cols].any(axis=1)
            st.dataframe(anomaly_df[anomaly_df['any_anomaly']].head(100), use_container_width=True)
    else:
        st.info("Run anomaly detection (Phase 2.2) to see results.")

st.markdown("---")
st.caption("Operations data from DuckDB | Quantum Bricks Analytics")