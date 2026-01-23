
import sys
import json
import time
import logging
from pathlib import Path

from config import RETRIEVAL_K, EMBEDDING_MODEL_NAME, JSON_DATA_PATH, DEFAULT_SCENARIO
from agent import RAGAgent
from logger_config import LOG_FORMAT

# 配置日志
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


# 开启 Ragas 的调试日志
logging.getLogger("ragas").setLevel(logging.DEBUG)

def batch_evaluate(agent: RAGAgent):
    """
    批量评估模式
    """
    print("\n=== 批量评估模式 ===")
    print("请输入测试集 JSON 文件路径 (格式: [{'question': '...', 'ground_truth': '...'}, ...])")
    print("或者直接回车使用默认内置测试用例。")
    
    test_file = input("路径: ").strip()
    
    test_data = []
    if test_file and Path(test_file).exists():
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                test_data = json.load(f)
        except Exception as e:
            logger.error(f"加载测试集失败: {e}")
            return
    else:
        # 默认测试用例
        print("使用默认测试用例...")
        test_data = [
            {"question": "李嘉敏是哪个部门的？", "ground_truth": "李嘉敏在开发部。"},
            {"question": "销售部有哪些人？", "ground_truth": "销售部有张三和李四。"}
        ]
    
    print(f"开始评估 {len(test_data)} 条用例...")
    
    results = []
    count = 0
    for item in test_data:
        count += 1
        q = item.get("question")
        gt = item.get("ground_truth")
        print(f"\nEvaluating: {q}")
        
        # 调用 chat 
        res = agent.chat(q, session_id=f"eval_{time.time()}_{count}", ground_truth=gt)
        
        # 收集结果
        eval_metrics = res.get("evaluation", {})
        
        # Handle different return types if needed, but RagasEvaluator returns dict now
        eval_dict = eval_metrics

        results.append({
            "question": q,
            "answer": res["answer"],
            "ground_truth": gt,
            "metrics": eval_dict
        })
        
        print(f"Answer: {res['answer']}")
        print(f"Metrics: {eval_dict}")
    
    # 汇总报告
    print("\n" + "="*50)
    print("=== 评估汇总报告 ===")
    avg_scores = {}
    valid_count = 0
    for r in results:
        metrics = r["metrics"]
        if not metrics: continue
        valid_count += 1
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                avg_scores[k] = avg_scores.get(k, 0) + v
    
    if valid_count > 0:
        for k in avg_scores:
            avg_scores[k] /= valid_count
            print(f"{k}: {avg_scores[k]:.4f}")
    else:
        print("无有效评估结果")
    print("="*50)

def main():
    agent = RAGAgent(scenario=DEFAULT_SCENARIO)
    
    print("=== RAG 智能问答系统 (Modularized) ===")
    print(f"当前配置: K={RETRIEVAL_K}, Embedding={EMBEDDING_MODEL_NAME}")
    print("1. 初始化/更新知识库 (加载 JSON)")
    print("2. 智能问答模式 (Auto Route: SQL/RAG)")
    print("3. 批量评估 (Batch Eval)")
    
    choice = input("请选择 (默认2): ").strip()
    
    if choice == "1":
        agent.reload_data(JSON_DATA_PATH)
        print("知识库加载完成！")
    elif choice == "3":
        batch_evaluate(agent)
        return
    
    session_id = f"user_{int(time.time())}"
    print(f"已创建新会话: {session_id}")
    
    while True:
        q = input("\n问题 (输入 'exit' 退出): ").strip()
        if not q: continue
        if q.lower() in ['exit', 'quit']: break
        
        gt = None
        
        # 统一使用智能路由
        result = agent.chat(q, session_id=session_id, ground_truth=gt)

        print("\n" + "="*50)
        print(f"🤖 回答:\n{result['answer']}")
        print("-" * 50)
        
        # 只有 RAG 模式才有 Ragas 评估
        if result.get('evaluation'):
            print("📊 Ragas 评估指标:")
            eval_res = result['evaluation']
            for k, v in eval_res.items():
                if isinstance(v, float) and (v != v): # Check for NaN
                    print(f"   {k}: N/A (模型生成格式错误)")
                else:
                    print(f"   {k}: {v:.4f}")
        else:
            print("📊 评估: 此为结构化查询(SQL)，跳过 Ragas 评估。")
        
        print("-" * 50)
        print("⏱️ 耗时统计:")
        timing = result.get('timing', {})
        print(f"   总耗时: {timing.get('total_ms', 0)} ms")
        
        # 动态展示所有记录的阶段耗时
        for k, v in timing.items():
            if k == 'total_ms': continue
            # 格式化一下key显示更友好
            label = k.replace('_ms', '').replace('_', ' ').capitalize()
            print(f"   {label}: {v} ms")
        
        print("-" * 50)
        print(f"📚 参考来源:")
        for i, src in enumerate(result['sources']):
            print(f"\n   --- Source {i+1} [ID: {src['chunk_id']}] ---")
            print(f"   {src['content'].strip()[:200]}...") # 限制长度避免刷屏

if __name__ == "__main__":
    main()
