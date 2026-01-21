"""
Phase 4.2 - Anomaly Explainer: LLM-generated root cause narratives
"""
import duckdb
import pandas as pd
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DUCKDB_PATH

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

EXPLAINER_PROMPT = """You are a supply chain analyst explaining anomalies to business stakeholders.

Given anomaly data, provide:
1. **Root Cause Hypothesis** - Most likely explanation (2-3 sentences)
2. **Business Impact** - Revenue/operational impact (1-2 sentences)  
3. **Recommended Action** - Specific next step (1 sentence)

Keep it concise and actionable. Use plain business language, not technical jargon.
"""

def get_anomaly_context(sku: str, store_id: str, ds: str) -> dict:
    """Fetch anomaly context from database"""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    
    # Get the anomaly record
    anomaly_sql = f"""
    SELECT * FROM main_features.anomalies 
    WHERE sku = '{sku}' AND store_id = '{store_id}' AND ds = '{ds}'
    """
    
    # Get historical context (7-day window)
    history_sql = f"""
    SELECT ds, units_sold, revenue, demand
    FROM main_features.demand_features
    WHERE sku = '{sku}' AND store_id = '{store_id}'
      AND ds BETWEEN DATE '{ds}' - INTERVAL '7 days' AND DATE '{ds}' + INTERVAL '1 day'
    ORDER BY ds
    """
    
    # Get SKU baseline stats
    baseline_sql = f"""
    SELECT 
        AVG(units_sold) as avg_units,
        STDDEV(units_sold) as std_units,
        AVG(revenue) as avg_revenue
    FROM main_features.demand_features
    WHERE sku = '{sku}' AND store_id = '{store_id}'
    """
    
    try:
        anomaly = con.execute(anomaly_sql).fetchdf()
        history = con.execute(history_sql).fetchdf()
        baseline = con.execute(baseline_sql).fetchdf()
        return {
            "anomaly": anomaly.to_dict('records')[0] if len(anomaly) > 0 else {},
            "history": history.to_dict('records'),
            "baseline": baseline.to_dict('records')[0] if len(baseline) > 0 else {}
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()

def explain_anomaly(sku: str, store_id: str, ds: str) -> str:
    """Generate LLM explanation for a specific anomaly"""
    context = get_anomaly_context(sku, store_id, ds)
    
    if "error" in context:
        return f"Could not fetch context: {context['error']}"
    
    prompt = f"""
Anomaly detected for SKU: {sku}, Store: {store_id}, Date: {ds}

Anomaly Details:
{context.get('anomaly', 'No anomaly record found')}

7-Day History:
{context.get('history', [])}

Baseline (all-time averages):
{context.get('baseline', {})}

Analyze this anomaly and provide your assessment.
"""
    
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": EXPLAINER_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def explain_top_anomalies(n: int = 5) -> list:
    """Get and explain top N anomalies by score"""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    
    # Try main anomalies table first
    sql = f"""
    SELECT sku, store_id, ds::VARCHAR as ds, anomaly_score, anomaly_type
    FROM main_features.anomalies
    WHERE is_anomaly = true
    ORDER BY anomaly_score DESC
    LIMIT {n}
    """
    
    try:
        top_anomalies = con.execute(sql).fetchdf()
    except:
        # Fallback: compute z-score from demand_features
        print("⚠️  Anomaly table not found. Computing from demand features...")
        sql = f"""
        SELECT sku, store_id, ds::VARCHAR as ds, 
               ABS(units_sold - units_sold_roll_mean_7) / NULLIF(units_sold_roll_std_7, 0) as anomaly_score,
               'zscore' as anomaly_type
        FROM main_features.demand_features
        WHERE units_sold_roll_std_7 > 0
        ORDER BY anomaly_score DESC
        LIMIT {n}
        """
        top_anomalies = con.execute(sql).fetchdf()
    finally:
        con.close()
    
    explanations = []
    for _, row in top_anomalies.iterrows():
        print(f"\n🔍 Analyzing: {row['sku']} @ {row['store_id']} on {row['ds']}...")
        explanation = explain_anomaly(row['sku'], row['store_id'], row['ds'])
        explanations.append({
            "sku": row['sku'],
            "store_id": row['store_id'],
            "date": row['ds'],
            "score": row['anomaly_score'],
            "type": row['anomaly_type'],
            "explanation": explanation
        })
        print(explanation)
    
    return explanations

if __name__ == "__main__":
    print("=" * 50)
    print("Quantum Bricks - Anomaly Explainer")
    print("=" * 50)
    
    # Explain top 3 anomalies
    results = explain_top_anomalies(n=3)
    
    # Save to file
    import json
    with open("anomaly_explanations.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✅ Saved {len(results)} explanations to anomaly_explanations.json")
