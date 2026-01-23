
import time
import logging
from typing import Dict, Any

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from config import (
    EMBEDDING_MODEL_NAME,
    CHAT_MODEL_NAME,
    LM_STUDIO_API_BASE,
    LM_STUDIO_API_KEY,
    JSON_DATA_PATH
)
from memory import SimpleMemory
from evaluator import RagasEvaluator
from sql_engine import StructuredQueryEngine
from retrieval_engine import RetrievalEngine
from logger_config import PhaseLogger

logger = logging.getLogger(__name__)

class RAGAgent:
    """
    总控 Agent：初始化、路由、交互
    """
    def __init__(self, scenario: str = "通用场景", json_path: str = None):
        self.phase_logger = PhaseLogger("RAGAgent")
        self.scenario = scenario
        # 优先使用传入的 json_path，否则使用配置中的默认路径
        self.json_path = json_path if json_path else JSON_DATA_PATH
        
        with self.phase_logger.phase("初始化"):
            # 1. Initialize Models
            self.embeddings = OpenAIEmbeddings(
                model=EMBEDDING_MODEL_NAME,
                openai_api_base=LM_STUDIO_API_BASE,
                openai_api_key=LM_STUDIO_API_KEY,
                check_embedding_ctx_length=False 
            )
            
            self.llm = ChatOpenAI(
                model=CHAT_MODEL_NAME,
                openai_api_base=LM_STUDIO_API_BASE,
                openai_api_key=LM_STUDIO_API_KEY,
                temperature=0.3,
                max_tokens=12800 
            )
            
            # 2. Initialize Components
            self.evaluator = RagasEvaluator(self.llm, self.embeddings)
            # 使用实例变量 self.json_path
            self.structured_engine = StructuredQueryEngine(self.llm, self.json_path)
            self.retrieval_engine = RetrievalEngine(self.llm, self.embeddings, self.evaluator)
            
            # 如果指定了非默认的 json_path，可能需要触发数据加载（视具体需求而定）
            # 这里暂时假设 StructuredQueryEngine 会在 init 时加载，RetrievalEngine 依赖 ingest 或持久化
            if json_path and json_path != JSON_DATA_PATH:
                logger.info(f"使用自定义数据路径: {json_path}")
                # 注意：RetrievalEngine 通常需要显式 ingest，这里为了测试方便，
                # 如果是全新的路径，可能需要调用 ingest_data。
                # 但为了避免启动过慢，我们假设测试用例会自己处理或只测 SQL。
                # 为了 test_generalization.py 能跑通 SQL，StructuredQueryEngine 已经够了。

            # 3. Memory Management
            self.sessions: Dict[str, SimpleMemory] = {}

    def get_memory(self, session_id: str) -> SimpleMemory:
        """获取或创建指定会话的内存"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SimpleMemory(k=5)
        return self.sessions[session_id]

    def reload_data(self, json_path: str = None):
        """重新加载所有数据"""
        target_path = json_path if json_path else self.json_path
        with self.phase_logger.phase("数据重载"):
            logger.info(f"正在重新加载所有数据: {target_path}...")
            self.structured_engine.reload_data(target_path)
            self.retrieval_engine.ingest_data(target_path)
            self.json_path = target_path # 更新当前路径
            logger.info("数据重新加载完成。")

    def classify_intent(self, question: str) -> str:
        """
        判断用户意图：是【聚合计算/统计查询】还是【非结构化检索】
        返回: 'SQL' 或 'RAG'
        """
        with self.phase_logger.phase("意图识别"):
            prompt = f"""
你是一个智能意图识别助手。当前服务的业务场景为：【{self.scenario}】。
请根据该场景背景，判断用户问题的类型。

用户问题: {question}

类型定义：
1. SQL (结构化查询): 涉及对数据库中具体字段的统计、计算、排序或精确筛选。
    - 特征：通常包含"多少"、"总和"、"平均"、"最大/最小"、"大于/小于"、"列出...的详情"等明确的数据操作指令，或者**查询特定实体的属性值**。
    - 示例："{self.scenario}中有多少条记录？"、"统计各部门人数"、"列出价格高于100的产品"、"张三的邮箱是什么"。
 2. RAG (知识检索): 涉及对非结构化文档、描述性文本或背景知识的查询。
    - 特征：通常询问"是什么"、"介绍一下"、"背景"、"流程"、"原因"等语义理解类问题。
    - 示例："介绍一下项目背景"、"如何处理退款流程"、"某人的主要职责是什么"。

请只返回类型名称（SQL 或 RAG），不要包含其他文字。
"""
            try:
                response = self.llm.invoke(prompt)
                intent = response.content.strip().upper()
                if "SQL" in intent: return "SQL"
                return "RAG"
            except Exception as e:
                logger.warning(f"Intent classification failed, defaulting to RAG: {e}")
                return "RAG" # 默认回退到RAG

    def chat(self, question: str, session_id: str = "default", ground_truth: str = None) -> Dict[str, Any]:
        """
        智能路由模式：自动选择 SQL 或 RAG，并支持失败自动回退
        """
        t_start = time.time()
        self.phase_logger.timings = {}
        
        # 1. 获取上下文
        with self.phase_logger.phase("上下文加载"):
            memory = self.get_memory(session_id)
            history_vars = memory.load_memory_variables({})
            history_str = history_vars.get("history", "")

        # 初始意图识别
        initial_intent = self.classify_intent(question)
        logger.info(f"初始意图识别结果: {initial_intent}")
        
        # 策略执行队列
        strategy_queue = [initial_intent]
        fallback_intent = "RAG" if initial_intent == "SQL" else "SQL"
        strategy_queue.append(fallback_intent)
        
        final_result = {}
        success = False
        
        for attempt, current_intent in enumerate(strategy_queue):
            logger.info(f"Attempt {attempt + 1}: Executing {current_intent} strategy...")
            
            if current_intent == "SQL":
                result = self._execute_sql(question, history_str)
            else:
                result = self._execute_rag(question, history_str, ground_truth)
                
            # 记录耗时
            self.phase_logger.timings.update(result.get("timing", {}))
            
            # 验证结果有效性
            if self._is_valid_answer(result, current_intent):
                final_result = result
                success = True
                logger.info(f"Strategy {current_intent} succeeded.")
                break
            else:
                logger.warning(f"Strategy {current_intent} failed to provide a valid answer.")
                final_result = result # 保留失败结果，以防万一
                # 如果这是最后一次尝试，最终结果就是这个失败的
                
        # 2. 保存上下文
        with self.phase_logger.phase("上下文保存"):
            if final_result.get("answer"):
                 memory.save_context({"input": question}, {"output": final_result["answer"]})

        t_end = time.time()
        if "timing" not in final_result: final_result["timing"] = {}
        final_result["timing"]["total_ms"] = round((t_end - t_start) * 1000, 2)
        
        return final_result

    def _execute_sql(self, question, history):
        logger.info("执行结构化查询 (Text-to-SQL)...")
        result_sql = self.structured_engine.query(question, history)
        return {
            "answer": result_sql["answer"],
            "sources": [{"chunk_id": "SQL", "content": f"SQL: {result_sql.get('sql')}\nRaw: {result_sql.get('raw_result')}"}],
            "evaluation": {}, 
            "timing": self.structured_engine.phase_logger.get_timings(),
            "raw_result": result_sql.get("raw_result"),
            "sql_query": result_sql.get("sql")
        }

    def _execute_rag(self, question, history, ground_truth):
        logger.info("执行非结构化检索 (Iterative RAG)...")
        result = self.retrieval_engine.iterative_search(question, history, ground_truth)
        return result

    def _is_valid_answer(self, result: Dict, intent: str) -> bool:
        answer = result.get("answer", "")
        if not answer: return False
        
        if intent == "SQL":
            # SQL 失败条件
            if answer.startswith("SQL执行出错") or answer == "无法生成有效的SQL查询。":
                return False
            raw = result.get("raw_result", "")
            if raw and "查询结果为空" in raw:
                return False
            if result.get("sql_query") is None:
                return False
            return True
            
        else: # RAG
            # RAG 失败条件
            if "根据知识库内容无法提供回答" in answer:
                return False
            return True
