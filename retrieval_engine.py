
import json
import time
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from config import DB_PERSIST_DIR, ENABLE_RAGAS_EVALUATION
from logger_config import PhaseLogger

logger = logging.getLogger(__name__)

class RetrievalEngine:
    """
    处理非结构化检索与迭代逻辑
    """
    def __init__(self, llm, embeddings, evaluator):
        self.phase_logger = PhaseLogger("RetrievalEngine")
        self.llm = llm
        self.embeddings = embeddings
        self.evaluator = evaluator
        
        # 初始化向量数据库
        with self.phase_logger.phase("向量库初始化"):
            self.vector_store = Chroma(
                persist_directory=DB_PERSIST_DIR,
                embedding_function=self.embeddings,
                collection_name="contact_list"
            )

    def ingest_data(self, json_path: str):
        """将 JSON 数据加载到向量数据库"""
        with self.phase_logger.phase("数据入库"):
            path = Path(json_path)
            if not path.exists():
                logger.error(f"数据文件不存在: {path}")
                return

            logger.info(f"开始加载数据: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logger.error("JSON 格式错误")
                    return

            documents = []
            debug_keyword = "李嘉敏"
            debug_found = False

            for entry in data:
                for chunk_uuid, chunk_data in entry.items():
                    content_list = chunk_data.get("content", [])
                    doc_id = chunk_data.get("doc_id", "")
                    chunk_id = chunk_data.get("chunk_id", "")
                    
                    text_content = ""
                    for row in content_list:
                        row_str = ", ".join([f"{k}:{v}" for k, v in row.items() if v])
                        text_content += row_str + "\n"
                    
                    if not text_content.strip():
                        continue

                    if debug_keyword in text_content:
                        debug_found = True
                        logger.info(f"DEBUG: 发现包含 '{debug_keyword}' 的Chunk ID: {chunk_id}")

                    doc = Document(
                        page_content=text_content,
                        metadata={
                            "doc_id": doc_id,
                            "chunk_id": chunk_id,
                            "original_json": json.dumps(content_list, ensure_ascii=False)
                        }
                    )
                    documents.append(doc)

            if documents:
                logger.info(f"准备存入 {len(documents)} 个文档块...")
                ids = [doc.metadata["chunk_id"] for doc in documents]
                self.vector_store.add_documents(documents=documents, ids=ids)
                
                if debug_found:
                    logger.info(f"确认: '{debug_keyword}' 已被包含在待入库文档中。")
                else:
                    logger.warning(f"警告: 待入库文档中未找到 '{debug_keyword}'，请检查JSON源文件。")

                count = self.vector_store._collection.count()
                logger.info(f"数据入库完成。当前数据库文档总数: {count}")
            else:
                logger.warning("没有解析到有效文档。")


    def _process_batch_judgment(self, question: str, accumulated_clues: str, current_contexts: List[str], history: str = "") -> Tuple[str, str, str]:
        """
        LLM 判断：当前资料是否足以回答问题，如果不足则生成下一步检索计划
        返回: (status, content/clues, next_query)
        status: 'SOLVED' | 'SEARCH_MORE' | 'GIVE_UP'
        """
        context_block = "\n".join([f"--- Doc {i+1} ---\n{txt}" for i, txt in enumerate(current_contexts)])
        
        system_prompt = """
你是一个智能检索助手。你的任务是判断提供的参考资料是否包含回答用户问题的完整信息。
严格遵守以下规则：
1. **禁止幻觉**：如果你在资料中找不到用户查询的确切ID、编号、姓名或关键词，**绝对不要**尝试猜测或使用仅仅是"看起来像"的数据，严禁强行关联。
2. **多轮检索**：如果当前资料不足或不匹配，请优先选择 "SEARCH_MORE" 并生成新的查询词，而不是直接 "GIVE_UP"。只有当你确定换个词也搜不到（比如已尝试过多种变体）时才放弃。
3. **精准匹配**：对于代码、订单号、款号等实体，必须精确匹配。
        """
        
        user_prompt = f"""
[历史对话]
{history if history else "无"}

[用户问题]
{question}

[已累积的线索]
{accumulated_clues if accumulated_clues else "无"}

[当前批次参考资料]
{context_block}

请仔细分析并按以下格式输出之一：

情况 1：资料足以完整回答问题
STATUS: SOLVED
CONTENT: [你的最终答案]

情况 2：资料不足，需要进一步检索
STATUS: SEARCH_MORE
CLUES: [从当前资料中提取的新线索总结，如果无新线索填"无"]
NEXT_QUERY: [用于查找缺失信息的新的搜索关键词，简短精确]

情况 3：资料不足且无法构造有效的新查询（已尽力）
STATUS: GIVE_UP
CLUES: [总结已知信息]

注意：
- NEXT_QUERY 应该是针对缺失信息的具体关键词（例如"营运部 人员名单" 或 "张三 职位"）。
- 不要再次搜索已经搜索过的词。
"""
        # --- 打印调试日志 ---
        logger.info(f"\n{'='*20} ROUND JUDGMENT START {'='*20}")
        # logger.info(f"Prompt:\n{user_prompt.strip()}") # 减少日志量
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            content = response.content.strip()
            
            logger.info(f"LLM Response:\n{content}")
            logger.info(f"{'='*20} ROUND JUDGMENT END {'='*20}\n")
            
            if "STATUS: SOLVED" in content:
                parts = content.split("CONTENT:", 1)
                answer = parts[1].strip() if len(parts) > 1 else content
                return "SOLVED", answer, ""
            
            elif "STATUS: SEARCH_MORE" in content:
                # 解析 CLUES 和 NEXT_QUERY
                clues_part = ""
                query_part = ""
                
                lines = content.split('\n')
                current_section = None
                for line in lines:
                    if "CLUES:" in line:
                        clues_part = line.split("CLUES:", 1)[1].strip()
                        current_section = "CLUES"
                    elif "NEXT_QUERY:" in line:
                        query_part = line.split("NEXT_QUERY:", 1)[1].strip()
                        current_section = "QUERY"
                    elif current_section == "CLUES":
                        clues_part += " " + line.strip()
                    # QUERY通常只有一行
                
                return "SEARCH_MORE", clues_part, query_part
            
            else:
                # Fallback to GIVE_UP or partial clues
                parts = content.split("CLUES:", 1)
                clues = parts[1].strip() if len(parts) > 1 else "无新线索"
                return "GIVE_UP", clues, ""
                
        except Exception as e:
            logger.error(f"Batch judgment failed: {e}")
            return "GIVE_UP", "Error in judgment", ""

    def iterative_search(self, question: str, history: str = "", ground_truth: str = None) -> Dict[str, Any]:
        """
        执行迭代式 RAG 流程 (Dynamic Iterative Retrieval)
        """
        # Reset timings for this call
        self.phase_logger.timings = {}
        
        MAX_ROUNDS = 5 # 动态检索比较慢，减少轮数
        BATCH_SIZE = 5 # 每次只看最相关的5个
        
        # logger.info(f"启动动态智能检索模式: Max {MAX_ROUNDS} rounds...") # REMOVED: Redundant log
        
        accumulated_clues = ""
        final_answer = ""
        used_sources = []
        seen_chunk_ids = set()
        
        current_query = question
        is_solved = False
        
        for round_idx in range(MAX_ROUNDS):
            round_key = f"第{round_idx+1}轮"
            
            with self.phase_logger.phase(f"{round_key}_总流程"):
                logger.info(f"Round {round_idx+1}: Searching for '{current_query}'...")
                
                # 1. 检索
                with self.phase_logger.phase(f"{round_key}_检索"):
                    docs = self.vector_store.similarity_search(current_query, k=BATCH_SIZE * 2) # 多取一些以便去重
                
                # 2. 去重与筛选
                current_batch_docs = []
                for doc in docs:
                    chunk_id = doc.metadata.get("chunk_id")
                    if chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        current_batch_docs.append(doc)
                        if len(current_batch_docs) >= BATCH_SIZE:
                            break
                
                if not current_batch_docs:
                    logger.info(f"Round {round_idx+1}: No new documents found.")
                    # 如果没有新文档，尝试强行让LLM基于现有信息总结，或者停止
                    if round_idx == 0:
                         return self._fallback_response("根据知识库内容无法提供回答", self.phase_logger.get_timings())
                    break
                
                # 记录来源
                current_contexts = []
                for doc in current_batch_docs:
                    current_contexts.append(doc.page_content)
                    used_sources.append({
                        "doc_id": doc.metadata.get("doc_id"),
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "content": doc.page_content
                    })
                
                # 3. LLM 判断与规划
                with self.phase_logger.phase(f"{round_key}_判读"):
                    status, output_content, next_query = self._process_batch_judgment(
                        question, accumulated_clues, current_contexts, history
                    )
                
                if status == "SOLVED":
                    logger.info(f"Round {round_idx+1}: Answer found!")
                    final_answer = output_content
                    is_solved = True
                    break
                
                elif status == "SEARCH_MORE":
                    logger.info(f"Round {round_idx+1}: Need more info. Next Query: '{next_query}'")
                    if output_content and "无新线索" not in output_content:
                        accumulated_clues += f"\n[Round {round_idx+1} Clues]: {output_content}"
                    
                    if next_query and len(next_query.strip()) > 1:
                        current_query = next_query
                    else:
                        logger.warning("LLM did not provide a valid next query. Stopping.")
                        break
                
                else: # GIVE_UP
                    logger.info("Round {round_idx+1}: LLM decided to give up searching.")
                    if output_content:
                        accumulated_clues += f"\n[Round {round_idx+1} Clues]: {output_content}"
                    break
        
        if not is_solved:
            with self.phase_logger.phase("最终总结"):
                logger.info("Generating final answer based on accumulated clues.")
                final_answer = self._generate_final_summary(question, accumulated_clues, history)
            
        all_contexts_text = [s['content'] for s in used_sources]
        
        evaluation_result = {}
        if ENABLE_RAGAS_EVALUATION:
            with self.phase_logger.phase("Ragas评估"):
                logger.info("正在进行 Ragas 评估...")
                evaluation_result = self.evaluator.evaluate_single(question, final_answer, all_contexts_text, ground_truth)
        else:
             logger.info("Ragas 评估已禁用 (ENABLE_RAGAS_EVALUATION=False)")

        return {
            "answer": final_answer,
            "sources": used_sources,
            "evaluation": evaluation_result,
            "timing": self.phase_logger.get_timings()
        }

    def _generate_final_summary(self, question, clues, history: str = ""):
        """当检索耗尽仍未找到确切答案时，基于线索总结"""
        prompt = Prompts.RAG_SUMMARY.format(
            history=history if history else "无",
            question=question,
            clues=clues
        )
        return self.llm.invoke(prompt).content

    def _fallback_response(self, msg, timing):
        return {
            "answer": msg,
            "sources": [],
            "evaluation": {},
            "timing": timing
        }
