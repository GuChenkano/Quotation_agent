import time
import logging
from typing import Dict, Any

# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_openai import ChatOpenAI
from custom_embeddings import CustomOpenAIEmbeddings

from config import (
    EMBEDDING_MODEL_NAME,
    CHAT_MODEL_NAME,
    LM_STUDIO_API_BASE,
    LM_STUDIO_API_KEY,
    JSON_DATA_PATH,
    Prompts
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
            self.embeddings = CustomOpenAIEmbeddings(
                model=EMBEDDING_MODEL_NAME,
                openai_api_base=LM_STUDIO_API_BASE,
                openai_api_key=LM_STUDIO_API_KEY
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
            
            # 4. 自动数据初始化检查
            # 检查向量库是否为空，如果为空则自动加载数据
            try:
                # 获取集合中的文档数量
                count = self.retrieval_engine.vector_store._collection.count()
                if count == 0:
                    logger.warning(f"检测到向量库为空 (count=0)，正在自动从 {self.json_path} 加载数据...")
                    if self.json_path:
                        self.retrieval_engine.ingest_data(self.json_path)
                    else:
                        logger.error("未指定 JSON 数据路径，无法执行自动入库。")
                else:
                    logger.info(f"向量库健康检查通过，当前文档总数: {count}")
            except Exception as e:
                logger.error(f"向量库自动检查/初始化失败: {e}")

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
            prompt = Prompts.INTENT_CLASSIFICATION.format(
                scenario=self.scenario,
                question=question
            )
            try:
                response = self.llm.invoke(prompt)
                intent = response.content.strip().upper()
                
                logger.info(f"[RAGAgent] - LLM意图识别输入: \"{question}\"")
                logger.info(f"[RAGAgent] - LLM意图识别输出: 意图=\"{intent}\", 置信度=\"未知\"")
                
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
        
        # Trace logs
        trace_log = []
        trace_log.append({
            "step": "Intent Recognition",
            "details": {
                "initial_intent": initial_intent,
                "history_used": history_str
            }
        })

        for attempt, current_intent in enumerate(strategy_queue):
            logger.info(f"Attempt {attempt + 1}: Executing {current_intent} strategy...")
            
            step_trace = {
                "step": f"Strategy Execution (Attempt {attempt + 1})",
                "strategy": current_intent,
                "details": {}
            }

            if current_intent == "SQL":
                result = self._execute_sql(question, history_str)
                step_trace["details"] = {
                    "type": "SQL",
                    "sql_query": result.get("sql_query"),
                    "raw_result": result.get("raw_result"),
                    "sql_attempts": result.get("sql_attempts") # 传递详细的 SQL 尝试记录
                }
            else:
                result = self._execute_rag(question, history_str, ground_truth)
                step_trace["details"] = {
                    "type": "RAG",
                    "rag_trace": result.get("trace", [])
                }
            
            trace_log.append(step_trace)

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
                
                if current_intent == "RAG":
                     # 尝试从 result 中提取更具体的失败信息，或者使用通用描述
                     # 在 RAG 失败时，通常是因为 "根据知识库内容无法提供回答"
                     # 我们需要判断是否是因为检索结果为 0。
                     # 我们可以检查 result 的 timing 是否很短，或者查看 trace（如果有）。
                     # 但最直接的是看 result['answer'] 是否是默认的失败消息。
                     rag_trace = result.get("trace", [])
                     is_no_docs = False
                     if rag_trace and len(rag_trace) > 0:
                         first_step = rag_trace[0]
                         if first_step.get("llm_judgment", {}).get("status") == "NO_DOCS":
                             is_no_docs = True
                     
                     timing_ms = result.get("timing", {}).get("total_ms", 0)
                     
                     if is_no_docs:
                         logger.warning(f"[agent] - RAG失败根因: 检索阶段返回0文档（耗时{timing_ms}ms），未进入生成阶段")
                         
                     if attempt < len(strategy_queue) - 1:
                         logger.info(f"[agent] - 触发策略回退: RAG检索结果为空，启用备用SQL策略")
                
                final_result = result # 保留失败结果，以防万一
                # 如果这是最后一次尝试，最终结果就是这个失败的
                
        # 2. 保存上下文
        with self.phase_logger.phase("上下文保存"):
            if final_result.get("answer"):
                 memory.save_context({"input": question}, {"output": final_result["answer"]})

        t_end = time.time()
        if "timing" not in final_result: final_result["timing"] = {}
        final_result["timing"]["total_ms"] = round((t_end - t_start) * 1000, 2)
        
        # 将 trace_log 添加到最终结果
        final_result["trace_log"] = trace_log
        
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
            "sql_query": result_sql.get("sql"),
            "sql_attempts": result_sql.get("sql_attempts", [])
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
