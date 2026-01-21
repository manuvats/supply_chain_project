"""
Phase 4 LLM Integration - Main Runner
Run all components or select individually
"""
import sys
import os

def print_menu():
    print("""
╔══════════════════════════════════════════════════╗
║   QUANTUM BRICKS - Phase 4 LLM Integration       ║
╠══════════════════════════════════════════════════╣
║  1. Text-to-SQL    - Natural language queries    ║
║  2. Anomaly Explainer - Root cause analysis      ║
║  3. Chat Assistant - Conversational interface    ║
║  4. Report Summarizer - Executive summaries      ║
║  5. Run All Tests                                ║
║  0. Exit                                         ║
╚══════════════════════════════════════════════════╝
    """)

def test_all():
    """Quick test of all components"""
    from text_to_sql import ask
    from anomaly_explainer import explain_top_anomalies
    from chat_assistant import SupplyChainAssistant
    from report_summarizer import generate_summary
    
    print("\n" + "="*50)
    print("TEST 1: Text-to-SQL")
    print("="*50)
    ask("What are the top 5 SKUs by revenue?", execute=True)
    
    print("\n" + "="*50)
    print("TEST 2: Anomaly Explainer")
    print("="*50)
    explain_top_anomalies(n=1)
    
    print("\n" + "="*50)
    print("TEST 3: Chat Assistant")
    print("="*50)
    assistant = SupplyChainAssistant()
    response = assistant.chat("Give me a quick overview of our data.")
    print(f"Assistant: {response}")
    
    print("\n" + "="*50)
    print("TEST 4: Report Summarizer")
    print("="*50)
    summary = generate_summary(period_days=30)
    print(summary)
    
    print("\n✅ All tests completed!")

def main():
    # Check API key
    from config import LLM_API_KEY
    if LLM_API_KEY == "your-api-key-here":
        print("⚠️  Please set GROQ_API_KEY environment variable or update config.py")
        print("   export GROQ_API_KEY='your-key-here'")
        return
    
    while True:
        print_menu()
        choice = input("Select option: ").strip()
        
        if choice == '0':
            print("Goodbye!")
            break
        elif choice == '1':
            from text_to_sql import ask
            while True:
                q = input("\nQuestion (or 'back'): ").strip()
                if q.lower() == 'back':
                    break
                ask(q)
        elif choice == '2':
            from anomaly_explainer import explain_top_anomalies
            n = input("How many anomalies to explain? [3]: ").strip() or "3"
            explain_top_anomalies(int(n))
        elif choice == '3':
            import chat_assistant
            chat_assistant.run_interactive()
        elif choice == '4':
            from report_summarizer import generate_full_report
            days = input("Period in days? [30]: ").strip() or "30"
            report = generate_full_report(int(days), "executive_summary.txt")
            print(report)
        elif choice == '5':
            test_all()
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()
