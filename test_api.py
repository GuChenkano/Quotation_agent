import logging
import sys
import json
from fastapi.testclient import TestClient
from api import app

# 配置日志显示
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_workflow():
    print("\n" + "="*50, flush=True)
    print("🚀 开始接口测试 (使用 TestClient 模拟)", flush=True)
    print("="*50, flush=True)

    try:
        # 使用 TestClient 上下文管理器，这会触发 lifespan (初始化 Agent)
        print("正在初始化 TestClient...", flush=True)
        with TestClient(app) as client:
            print("TestClient 初始化完成", flush=True)
            
            # 1. 健康检查
            print("\n[Step 1] 检查服务健康状态...", flush=True)
            response = client.get("/health")
            print(f"Status Code: {response.status_code}", flush=True)
            print(f"Response: {response.json()}", flush=True)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            # 2. 模拟用户提问 - SQL 场景
            question_sql = "财务部有几个人？"
            print(f"\n[Step 2] 模拟提问 (SQL场景): '{question_sql}'", flush=True)
            payload = {
                "question": question_sql,
                "session_id": "test_session_001"
            }
            
            response = client.post("/chat", json=payload)
            print(f"Status Code: {response.status_code}", flush=True)
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ API 响应成功:", flush=True)
                print(f"   Answer: {data['answer']}", flush=True)
                print(f"   SQL Query: {data.get('sql_query', 'N/A')}", flush=True)
                print(f"   Total Time: {data.get('timing', {}).get('total_ms', 0)} ms", flush=True)
                
                # 验证 Trace Log
                print("\n   [Trace Log Validation]")
                trace_log = data.get("trace_log", [])
                if trace_log:
                    print(f"   Found {len(trace_log)} trace steps.")
                    for step in trace_log:
                        print(f"   - Step: {step['step']}")
                        if step['step'] == 'Intent Recognition':
                             print(f"     -> Intent: {step['details'].get('initial_intent')}")
                else:
                    print("   ❌ Warning: No trace_log found!")

            else:
                print(f"❌ API 请求失败: {response.text}", flush=True)

            # 3. 模拟用户提问 - RAG 场景
            question_rag = "李鹏飞是谁"
            print(f"\n[Step 3] 模拟提问 (RAG场景): '{question_rag}'", flush=True)
            payload["question"] = question_rag
            
            response = client.post("/chat", json=payload)
            if response.status_code == 200:
                data = response.json()
                print("\n✅ API 响应成功:", flush=True)
                print(f"   Answer: {data['answer']}", flush=True)
                
                # 验证 Trace Log for RAG
                print("\n   [Trace Log Validation]")
                trace_log = data.get("trace_log", [])
                if trace_log:
                    print(f"   Found {len(trace_log)} trace steps.")
                    for step in trace_log:
                        print(f"   - Step: {step['step']}")
                        if "Strategy Execution" in step['step'] and step['details'].get('type') == 'RAG':
                             rag_trace = step['details'].get('rag_trace', [])
                             print(f"     -> RAG Rounds: {len(rag_trace)}")
                             if rag_trace:
                                 print(f"     -> Round 1 Query: {rag_trace[0].get('query')}")
                else:
                    print("   ❌ Warning: No trace_log found!")
                    
            else:
                print(f"❌ API 请求失败: {response.text}", flush=True)

    except Exception as e:
        print(f"❌ 测试过程中发生严重异常: {e}", flush=True)
        import traceback
        traceback.print_exc()

    print("\n" + "="*50, flush=True)
    print("🏁 测试结束", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    test_workflow()
