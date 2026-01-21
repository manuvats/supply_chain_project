"""
Phase 4 LLM Integration - Streamlit Dashboard
Unified interface for all LLM components
"""
import streamlit as st
import duckdb
import pandas as pd
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DUCKDB_PATH, SCHEMA_INFO

# Page config
st.set_page_config(
    page_title="Quantum Bricks - LLM Assistant",
    page_icon="🤖",
    layout="wide"
)

# Initialize LLM client
@st.cache_resource
def get_llm_client():
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

client = get_llm_client()

# Database connection
@st.cache_resource
def get_db_connection():
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)

# ============== TEXT-TO-SQL ==============
def text_to_sql_page():
    st.header("🔍 Text-to-SQL Query")
    st.caption("Ask questions in natural language, get SQL + results")
    
    # Example questions
    with st.expander("💡 Example Questions"):
        examples = [
            "What are the top 10 SKUs by total revenue?",
            "Show daily sales trend for the last 30 days",
            "Which stores have the most anomalies?",
            "What's the average units sold by day of week?",
            "Find SKUs with revenue over 10000",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex[:20]}"):
                st.session_state.sql_question = ex
    
    # Input
    question = st.text_input(
        "Your question:",
        value=st.session_state.get("sql_question", ""),
        placeholder="e.g., What are the top selling products?"
    )
    
    col1, col2 = st.columns([1, 5])
    with col1:
        run_query = st.button("🚀 Run", type="primary")
    with col2:
        show_sql = st.checkbox("Show generated SQL", value=True)
    
    if run_query and question:
        with st.spinner("Generating SQL..."):
            # Generate SQL
            system_prompt = f"""You are a SQL expert. Convert natural language to DuckDB SQL.
{SCHEMA_INFO}
Rules:
- Return ONLY the SQL query, no explanations
- Limit results to 20 rows unless specified
- Use DATE functions for date filtering"""
            
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0
            )
            sql = response.choices[0].message.content.strip()
            sql = sql.replace("```sql", "").replace("```", "").strip()
        
        if show_sql:
            st.code(sql, language="sql")
        
        # Execute
        try:
            con = get_db_connection()
            df = con.execute(sql).fetchdf()
            st.success(f"✅ {len(df)} rows returned")
            st.dataframe(df, use_container_width=True)
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, "query_results.csv", "text/csv")
        except Exception as e:
            st.error(f"❌ Query error: {e}")

# ============== ANOMALY EXPLAINER ==============
def anomaly_explainer_page():
    st.header("🔎 Anomaly Explainer")
    st.caption("AI-generated root cause analysis for detected anomalies")
    
    con = get_db_connection()
    
    # Fetch top anomalies
    try:
        sql = """
        SELECT sku, store_id, ds::VARCHAR as ds, anomaly_score, anomaly_type
        FROM main_features.anomalies
        WHERE is_anomaly = true
        ORDER BY anomaly_score DESC
        LIMIT 20
        """
        anomalies_df = con.execute(sql).fetchdf()
    except:
        # Fallback
        sql = """
        SELECT sku, store_id, ds::VARCHAR as ds, 
               ABS(units_sold - units_sold_roll_mean_7) / NULLIF(units_sold_roll_std_7, 0) as anomaly_score,
               'zscore' as anomaly_type
        FROM main_features.demand_features
        WHERE units_sold_roll_std_7 > 0
        ORDER BY anomaly_score DESC
        LIMIT 20
        """
        anomalies_df = con.execute(sql).fetchdf()
    
    if anomalies_df.empty:
        st.warning("No anomalies found in database")
        return
    
    # Display anomalies table
    st.subheader("Top Anomalies")
    st.dataframe(anomalies_df, use_container_width=True)
    
    # Select anomaly to explain
    st.subheader("Get AI Explanation")
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_sku = st.selectbox("SKU", anomalies_df['sku'].unique())
    with col2:
        sku_stores = anomalies_df[anomalies_df['sku'] == selected_sku]['store_id'].unique()
        selected_store = st.selectbox("Store", sku_stores)
    with col3:
        sku_store_dates = anomalies_df[
            (anomalies_df['sku'] == selected_sku) & 
            (anomalies_df['store_id'] == selected_store)
        ]['ds'].unique()
        selected_date = st.selectbox("Date", sku_store_dates)
    
    if st.button("🔍 Explain This Anomaly", type="primary"):
        with st.spinner("Analyzing anomaly..."):
            # Get context
            context_sql = f"""
            SELECT ds, units_sold, revenue, demand
            FROM main_features.demand_features
            WHERE sku = '{selected_sku}' AND store_id = '{selected_store}'
              AND ds BETWEEN DATE '{selected_date}' - INTERVAL '7 days' AND DATE '{selected_date}' + INTERVAL '1 day'
            ORDER BY ds
            """
            history = con.execute(context_sql).fetchdf()
            
            baseline_sql = f"""
            SELECT AVG(units_sold) as avg_units, STDDEV(units_sold) as std_units
            FROM main_features.demand_features
            WHERE sku = '{selected_sku}' AND store_id = '{selected_store}'
            """
            baseline = con.execute(baseline_sql).fetchdf()
            
            # Get anomaly details
            anomaly_row = anomalies_df[
                (anomalies_df['sku'] == selected_sku) & 
                (anomalies_df['store_id'] == selected_store) &
                (anomalies_df['ds'] == selected_date)
            ].iloc[0]
            
            prompt = f"""
Anomaly detected for SKU: {selected_sku}, Store: {selected_store}, Date: {selected_date}
Anomaly Score: {anomaly_row['anomaly_score']:.2f}, Type: {anomaly_row['anomaly_type']}

7-Day History:
{history.to_string()}

Baseline (all-time): Avg units = {baseline['avg_units'].values[0]:.1f}, Std = {baseline['std_units'].values[0]:.1f}

Provide:
1. **Root Cause Hypothesis** (2-3 sentences)
2. **Business Impact** (1-2 sentences)
3. **Recommended Action** (1 sentence)
"""
            
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a supply chain analyst explaining anomalies to business stakeholders. Be concise and actionable."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            st.markdown("### 📋 Analysis")
            st.markdown(response.choices[0].message.content)
            
            # Show history chart
            st.markdown("### 📈 7-Day Trend")
            st.line_chart(history.set_index('ds')['units_sold'])

# ============== CHAT ASSISTANT ==============
def chat_assistant_page():
    st.header("💬 Supply Chain Assistant")
    st.caption("Conversational interface for insights")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Get warehouse summary for context
    @st.cache_data(ttl=300)
    def get_summary():
        con = get_db_connection()
        sql = """
        SELECT 
            COUNT(*) as records,
            COUNT(DISTINCT sku) as skus,
            COUNT(DISTINCT store_id) as stores,
            SUM(revenue) as total_revenue
        FROM main_features.demand_features
        """
        return con.execute(sql).fetchdf().to_dict('records')[0]
    
    summary = get_summary()
    
    # Sidebar context
    with st.sidebar:
        st.markdown("### 📊 Data Context")
        st.metric("Records", f"{summary['records']:,}")
        st.metric("SKUs", summary['skus'])
        st.metric("Stores", summary['stores'])
        st.metric("Total Revenue", f"${summary['total_revenue']:,.0f}")
        
        if st.button("🔄 Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about your supply chain..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                system_prompt = f"""You are a supply chain analytics assistant for Quantum Bricks.
{SCHEMA_INFO}

Current data: {summary['records']:,} records, {summary['skus']} SKUs, {summary['stores']} stores, ${summary['total_revenue']:,.0f} total revenue.

Be concise, business-focused, and use specific numbers when available."""
                
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(st.session_state.messages)
                
                response = client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    temperature=0.4
                )
                
                reply = response.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

# ============== REPORT SUMMARIZER ==============
def report_summarizer_page():
    st.header("📄 Executive Report Generator")
    st.caption("Auto-generate summaries from your data")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        period = st.selectbox("Report Period", [7, 14, 30, 60, 90], index=2)
    with col2:
        report_type = st.radio("Report Type", ["Executive Summary", "Performance Deep Dive", "Anomaly Report"], horizontal=True)
    
    if st.button("📝 Generate Report", type="primary"):
        con = get_db_connection()
        
        with st.spinner("Fetching data and generating report..."):
            # Fetch data
            kpis = con.execute(f"""
                SELECT SUM(revenue) as revenue, SUM(units_sold) as units, COUNT(DISTINCT sku) as skus
                FROM main_features.demand_features
                WHERE ds >= (SELECT MAX(ds) - INTERVAL '{period} days' FROM main_features.demand_features)
            """).fetchdf().to_dict('records')[0]
            
            top_skus = con.execute(f"""
                SELECT sku, SUM(revenue) as revenue
                FROM main_features.demand_features
                WHERE ds >= (SELECT MAX(ds) - INTERVAL '{period} days' FROM main_features.demand_features)
                GROUP BY sku ORDER BY revenue DESC LIMIT 5
            """).fetchdf()
            
            bottom_skus = con.execute(f"""
                SELECT sku, SUM(revenue) as revenue
                FROM main_features.demand_features
                WHERE ds >= (SELECT MAX(ds) - INTERVAL '{period} days' FROM main_features.demand_features)
                GROUP BY sku ORDER BY revenue ASC LIMIT 5
            """).fetchdf()
            
            try:
                anomaly_count = con.execute(f"""
                    SELECT COUNT(*) as cnt FROM main_features.anomalies
                    WHERE is_anomaly = true AND ds >= (SELECT MAX(ds) - INTERVAL '{period} days' FROM main_features.demand_features)
                """).fetchone()[0]
            except:
                anomaly_count = "N/A"
            
            # Generate report
            prompt = f"""
Generate a {report_type} for Quantum Bricks supply chain.
Period: Last {period} days

KPIs: Revenue=${kpis['revenue']:,.0f}, Units={kpis['units']:,}, Active SKUs={kpis['skus']}
Top 5 SKUs: {top_skus.to_dict('records')}
Bottom 5 SKUs: {bottom_skus.to_dict('records')}
Anomalies Detected: {anomaly_count}

Format with clear sections and bullet points. Be specific with numbers.
"""
            
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a business analyst creating executive reports. Be professional, data-driven, and concise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            report = response.choices[0].message.content
        
        # Display report
        st.markdown("---")
        st.markdown(report)
        
        # Download options
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Download as TXT", report, f"report_{period}d.txt", "text/plain")
        with col2:
            st.download_button("📥 Download as MD", report, f"report_{period}d.md", "text/markdown")

# ============== MAIN ==============
def main():
    st.sidebar.title("🤖 LLM Assistant")
    
    # Check API key
    if LLM_API_KEY == "your-api-key-here":
        st.error("⚠️ Please set GROQ_API_KEY in config.py or environment variable")
        st.stop()
    
    page = st.sidebar.radio(
        "Select Tool",
        ["🔍 Text-to-SQL", "🔎 Anomaly Explainer", "💬 Chat Assistant", "📄 Report Generator"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Model: {LLM_MODEL}")
    
    if page == "🔍 Text-to-SQL":
        text_to_sql_page()
    elif page == "🔎 Anomaly Explainer":
        anomaly_explainer_page()
    elif page == "💬 Chat Assistant":
        chat_assistant_page()
    elif page == "📄 Report Generator":
        report_summarizer_page()

if __name__ == "__main__":
    main()
