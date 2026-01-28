import logging
import json
from sql_engine import StructuredQueryEngine
from langchain_openai import ChatOpenAI
from config import CHAT_MODEL_NAME, LM_STUDIO_API_BASE, LM_STUDIO_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sql_optimization():
    print("Initializing LLM...")
    llm = ChatOpenAI(
        model=CHAT_MODEL_NAME,
        openai_api_base=LM_STUDIO_API_BASE,
        openai_api_key=LM_STUDIO_API_KEY,
        temperature=0
    )
    
    json_path = r"d:\DM\LangChain\联络名单-Agent\Quotation_agent\test_data_sql.json"
    print(f"Initializing SQL Engine with {json_path}...")
    engine = StructuredQueryEngine(llm, json_path)
    
    # Test Case: Tricky Entity Mapping
    # The data has "部门" and "归属部门".
    # Let's ask about "财务部", which appears in both columns for different people.
    # But wait, in my dummy data:
    # Row 1: 部门=财务部
    # Row 3: 归属部门=财务部
    # If the user asks "财务部有多少人?", the system should ideally check both or pick the most likely.
    # Let's see if it can find the one that yields results or if the iterative process works.
    
    question = "财务部有几个人？"
    print(f"\nTesting Question: {question}")
    
    result = engine.query(question)
    
    print("\n--- Final Result ---")
    print(f"Answer: {result['answer']}")
    print(f"SQL: {result['sql']}")
    print(f"Raw Result: {result['raw_result']}")
    
    # Verification
    # It should have triggered the column analysis.
    # We can't easily assert internal state here without mocking, but we can check the logs if we run this.

if __name__ == "__main__":
    test_sql_optimization()
