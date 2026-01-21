"""
Page 1: Executive Dashboard
KPIs, revenue trends, forecast accuracy metrics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import duckdb

st.set_page_config(page_title="Executive Dashboard", page_icon="📊", layout="wide")

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DUCKDB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"

@st.cache_data(ttl=3600)
def load_data():
    """Load data from DuckDB."""
    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        
        # Daily aggregates
        daily_df = conn.execute("""
            SELECT 
                ds as date,
                SUM(revenue) as revenue,
                SUM(units_sold) as units_sold,
                COUNT(DISTINCT sku) as active_skus,
                COUNT(DISTINCT store_id) as active_stores
            FROM main_features.demand_features
            GROUP BY date
            ORDER BY date
        """).fetchdf()
        
        # SKU performance
        sku_df = conn.execute("""
            SELECT 
                sku,
                SUM(revenue) as total_revenue,
                SUM(units_sold) as total_units,
                AVG(units_sold) as avg_daily_units
            FROM main_features.demand_features
            GROUP BY sku
            ORDER BY total_revenue DESC
            LIMIT 20
        """).fetchdf()
        
        conn.close()
        return daily_df, sku_df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=3600)
def load_forecast_metrics():
    """Load model comparison results."""
    metrics_path = PROJECT_ROOT / "outputs" / "model_comparison_results.csv"
    if metrics_path.exists():
        return pd.read_csv(metrics_path)
    return pd.DataFrame()

# Load data
daily_df, sku_df = load_data()
forecast_df = load_forecast_metrics()

# Header
st.markdown("# 📊 Executive Dashboard")
st.markdown("Real-time business performance and forecast accuracy")
st.markdown("---")

# Top KPIs
if not daily_df.empty:
    total_revenue = daily_df['revenue'].sum()
    total_units = daily_df['units_sold'].sum()
    avg_daily_revenue = daily_df['revenue'].mean()
    
    # Trend (last 7 days vs prior 7 days)
    if len(daily_df) >= 14:
        recent = daily_df.tail(7)['revenue'].sum()
        prior = daily_df.tail(14).head(7)['revenue'].sum()
        trend = ((recent - prior) / prior * 100) if prior > 0 else 0
    else:
        trend = 0
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Revenue", f"${total_revenue:,.0f}", f"{trend:+.1f}% WoW")
    k2.metric("Units Sold", f"{total_units:,.0f}")
    k3.metric("Avg Daily Revenue", f"${avg_daily_revenue:,.0f}")
    k4.metric("Active SKUs", f"{daily_df['active_skus'].max():,}")

st.markdown("---")

# Charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("Revenue Trend")
    if not daily_df.empty:
        fig = px.area(daily_df, x='date', y='revenue', color_discrete_sequence=['#2d5a87'])
        fig.update_layout(xaxis_title="", yaxis_title="Revenue ($)", margin=dict(l=0, r=0, t=10, b=0))
        fig.update_traces(fill='tozeroy', line_shape='spline')
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Units Sold (Last 30 Days)")
    if not daily_df.empty:
        fig = px.bar(daily_df.tail(30), x='date', y='units_sold', color_discrete_sequence=['#10b981'])
        fig.update_layout(xaxis_title="", yaxis_title="Units", margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Top SKUs
col3, col4 = st.columns(2)

with col3:
    st.subheader("Top 10 SKUs by Revenue")
    if not sku_df.empty:
        fig = px.bar(sku_df.head(10), x='total_revenue', y='sku', orientation='h',
                     color='total_revenue', color_continuous_scale='Blues')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, 
                          xaxis_title="Revenue ($)", yaxis_title="", showlegend=False,
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("🎯 Forecast Model Performance")
    if not forecast_df.empty:
        agg_df = forecast_df[forecast_df['segment'] == 'all_items'] if 'segment' in forecast_df.columns else forecast_df
        if not agg_df.empty and 'wape' in agg_df.columns:
            fig = px.bar(agg_df.sort_values('wape'), x='model', y='wape',
                         color='wape', color_continuous_scale='RdYlGn_r')
            fig.update_layout(xaxis_title="Model", yaxis_title="WAPE (lower=better)",
                              showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run model comparison (Phase 2.3) to see forecast metrics.")

st.markdown("---")
st.caption("Data from DuckDB warehouse | Quantum Bricks Analytics")