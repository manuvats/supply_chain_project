"""
Phase 4.1 - Text-to-SQL: Natural Language Queries on DuckDB
"""
import duckdb
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, DUCKDB_PATH, SCHEMA_INFO

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

SYSTEM_PROMPT = f"""You are a SQL expert for a supply chain analytics database.
Convert natural language questions to DuckDB SQL queries.

{SCHEMA_INFO}

Rules:
- Return ONLY the SQL query, no explanations
- Use appropriate aggregations and filters
- Limit results to 20 rows unless user specifies
- Use DATE functions for date filtering (e.g., ds >= '2024-01-01')
- For "recent" data, use: ds >= CURRENT_DATE - INTERVAL '30 days'
"""

def text_to_sql(question: str) -> str:
    """Convert natural language to SQL"""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ],
        temperature=0
    )
    sql = response.choices[0].message.content.strip()
    # Clean markdown code blocks if present
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

def execute_query(sql: str):
    """Execute SQL and return results"""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        result = con.execute(sql).fetchdf()
        return result
    finally:
        con.close()

def ask(question: str, execute: bool = True):
    """Main interface: question -> SQL -> results"""
    print(f"\n📝 Question: {question}")
    
    sql = text_to_sql(question)
    print(f"\n🔧 Generated SQL:\n{sql}")
    
    if execute:
        try:
            df = execute_query(sql)
            print(f"\n📊 Results ({len(df)} rows):")
            print(df.to_string())
            return df
        except Exception as e:
            print(f"\n❌ Execution error: {e}")
            return None
    return sql

# Interactive mode
if __name__ == "__main__":
    print("=" * 50)
    print("Quantum Bricks - Text-to-SQL Interface")
    print("=" * 50)
    print("Ask questions in natural language. Type 'quit' to exit.\n")
    
    # Example questions
    examples = [
        "What are the top 10 SKUs by total revenue?",
        "Show daily sales trend for last 30 days",
        "Which stores have the highest anomaly rates?",
        "What's the average units sold per day of week?",
    ]
    print("Example questions:")
    for i, q in enumerate(examples, 1):
        print(f"  {i}. {q}")
    print()
    
    while True:
        question = input("\n🔍 Your question: ").strip()
        if question.lower() in ('quit', 'exit', 'q'):
            break
        if question:
            ask(question)
