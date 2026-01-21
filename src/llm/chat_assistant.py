"""
Phase 4.3 - Conversational Assistant: Chat interface for supply chain insights
"""
import duckdb
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DUCKDB_PATH, SCHEMA_INFO

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# Preload key metrics for context
def get_warehouse_summary() -> str:
    """Get current state summary from warehouse"""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    
    summaries = []
    
    queries = {
        "overview": """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT sku) as unique_skus,
                COUNT(DISTINCT store_id) as unique_stores,
                MIN(ds) as date_from,
                MAX(ds) as date_to
            FROM main_features.demand_features
        """,
        "recent_performance": """
            SELECT 
                SUM(revenue) as total_revenue,
                SUM(units_sold) as total_units,
                AVG(units_sold) as avg_daily_units
            FROM main_features.demand_features
            WHERE ds >= (SELECT MAX(ds) - INTERVAL '30 days' FROM main_features.demand_features)
        """,
        "top_skus": """
            SELECT sku, SUM(revenue) as revenue
            FROM main_features.demand_features
            GROUP BY sku ORDER BY revenue DESC LIMIT 5
        """
    }
    
    try:
        for name, sql in queries.items():
            df = con.execute(sql).fetchdf()
            summaries.append(f"{name}: {df.to_dict('records')}")
        return "\n".join(summaries)
    except Exception as e:
        return f"Error loading summary: {e}"
    finally:
        con.close()

SYSTEM_PROMPT = f"""You are a supply chain analytics assistant for "Quantum Bricks" - a retail company.

You have access to a data warehouse with demand forecasting features, anomaly detection results, and sales data.

{SCHEMA_INFO}

Current Warehouse State:
{{warehouse_summary}}

Capabilities:
1. Answer questions about sales trends, inventory, and demand patterns
2. Explain anomalies and their business impact
3. Provide recommendations for inventory optimization
4. Compare SKU/store performance

Guidelines:
- Be concise and business-focused
- Use specific numbers when available
- Suggest follow-up analyses when relevant
- If you need to query data, say "Let me check the data..." and describe what you'd look for
"""

class SupplyChainAssistant:
    def __init__(self):
        self.history = []
        self.warehouse_summary = get_warehouse_summary()
        self.system_prompt = SYSTEM_PROMPT.format(warehouse_summary=self.warehouse_summary)
    
    def chat(self, user_message: str) -> str:
        """Send message and get response"""
        self.history.append({"role": "user", "content": user_message})
        
        messages = [{"role": "system", "content": self.system_prompt}] + self.history
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.4
        )
        
        assistant_message = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    
    def clear_history(self):
        """Reset conversation"""
        self.history = []
        print("🔄 Conversation history cleared.")

def run_interactive():
    """Interactive chat loop"""
    print("=" * 50)
    print("Quantum Bricks - Supply Chain Assistant")
    print("=" * 50)
    print("Commands: 'clear' to reset, 'quit' to exit\n")
    
    assistant = SupplyChainAssistant()
    
    # Suggested questions
    suggestions = [
        "What's our overall sales performance?",
        "Which SKUs are underperforming?",
        "Are there any concerning anomalies this month?",
        "How can we optimize inventory for top sellers?",
    ]
    print("Try asking:")
    for s in suggestions:
        print(f"  • {s}")
    print()
    
    while True:
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        if user_input.lower() in ('quit', 'exit', 'q'):
            print("Goodbye!")
            break
        if user_input.lower() == 'clear':
            assistant.clear_history()
            continue
        
        response = assistant.chat(user_input)
        print(f"\n🤖 Assistant: {response}\n")

if __name__ == "__main__":
    run_interactive()
