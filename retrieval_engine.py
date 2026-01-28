import json
import time
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from config import DB_PERSIST_DIR, ENABLE_RAGAS_EVALUATION, Prompts
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


    def _process_batch_judgment(self, question: str, accumulated_clues: str, current_contexts: List[str], history: str = "") -> Tuple[str, str, str, Dict[str, Any]]:
        """
        LLM 判断：当前资料是否足以回答问题，如果不足则生成下一步检索计划
        返回: (status, content/clues, next_query, debug_info)
        status: 'SOLVED' | 'SEARCH_MORE' | 'GIVE_UP'
        """
        context_block = "\n".join([f"--- Doc {i+1} ---\n{txt}" for i, txt in enumerate(current_contexts)])
        
        system_prompt = Prompts.RAG_JUDGMENT_SYSTEM
        
        user_prompt = Prompts.RAG_JUDGMENT_USER.format(
            history=history if history else "无",
            question=question,
            accumulated_clues=accumulated_clues if accumulated_clues else "无",
            context_block=context_block
        )
        
        full_prompt = f"System:\n{system_prompt}\n\nUser:\n{user_prompt}"
        
        # --- 打印调试日志 ---
        logger.info(f"\n{'='*20} ROUND JUDGMENT START {'='*20}")
        
        start_time = time.time()
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            end_time = time.time()
            content = response.content.strip()
            
            debug_info = {
                "full_prompt": full_prompt,
                "llm_response": content,
                "response_time_ms": round((end_time - start_time) * 1000, 2),
                "context_strategy": "Direct Concatenation with History and Accumulated Clues"
            }
            
            logger.info(f"LLM Response:\n{content}")
            logger.info(f"{'='*20} ROUND JUDGMENT END {'='*20}\n")
            
            if "STATUS: SOLVED" in content:
                parts = content.split("CONTENT:", 1)
                answer = parts[1].strip() if len(parts) > 1 else content
                return "SOLVED", answer, "", debug_info
            
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
                
                return "SEARCH_MORE", clues_part, query_part, debug_info
            
            else:
                # Fallback to GIVE_UP or partial clues
                parts = content.split("CLUES:", 1)
                clues = parts[1].strip() if len(parts) > 1 else "无新线索"
                return "GIVE_UP", clues, "", debug_info
                
        except Exception as e:
            logger.error(f"Batch judgment failed: {e}")
            return "GIVE_UP", "Error in judgment", "", {"error": str(e)}

    def iterative_search(self, question: str, history: str = "", ground_truth: str = None) -> Dict[str, Any]:
        """
        执行迭代式 RAG 流程 (Dynamic Iterative Retrieval)
        """
        # Reset timings for this call
        self.phase_logger.timings = {}
        
        MAX_ROUNDS = 5 # 动态检索比较慢，减少轮数
        BATCH_SIZE = 5 # 每次只看最相关的5个
        
        accumulated_clues = ""
        final_answer = ""
        used_sources = []
        seen_chunk_ids = set()
        
        current_query = question
        is_solved = False
        
        trace_steps = []  # 记录每轮详细信息

        for round_idx in range(MAX_ROUNDS):
            round_key = f"第{round_idx+1}轮"
            step_info = {
                "round": round_idx + 1,
                "query": current_query,
                "retrieved_docs": [],
                "llm_judgment": {},
                "context_details": {}, # 新增上下文详情
                "generation_details": {} # 新增生成详情
            }
            
            with self.phase_logger.phase(f"{round_key}_总流程"):
                logger.info(f"Round {round_idx+1}: Searching for '{current_query}'...")
                
                # 1. 检索 (带分数)
                with self.phase_logger.phase(f"{round_key}_检索"):
                    # 改用 similarity_search_with_score
                    docs_with_scores = self.vector_store.similarity_search_with_score(current_query, k=BATCH_SIZE * 2)
                
                # 2. 去重与筛选
                current_batch_docs = []
                for doc, score in docs_with_scores:
                    chunk_id = doc.metadata.get("chunk_id")
                    if chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        current_batch_docs.append((doc, score))
                        if len(current_batch_docs) >= BATCH_SIZE:
                            break
                
                if not current_batch_docs:
                    logger.info(f"Round {round_idx+1}: No new documents found.")
                    step_info["retrieved_docs"] = []
                    step_info["llm_judgment"] = {"status": "NO_DOCS", "note": "No new documents found"}
                    trace_steps.append(step_info)
                    
                    if round_idx == 0:
                         return self._fallback_response("根据知识库内容无法提供回答", self.phase_logger.get_timings())
                    break
                
                # 记录来源
                current_contexts = []
                for doc, score in current_batch_docs:
                    current_contexts.append(doc.page_content)
                    doc_info = {
                        "doc_id": doc.metadata.get("doc_id"),
                        "chunk_id": doc.metadata.get("chunk_id"),
                        "content": doc.page_content,
                        "relevance_score": score, # 记录分数 (Chroma默认是L2距离，越小越相似; 或cosine距离)
                        "metadata": doc.metadata
                    }
                    used_sources.append(doc_info)
                    step_info["retrieved_docs"].append(doc_info)
                
                # 3. LLM 判断与规划
                with self.phase_logger.phase(f"{round_key}_判读"):
                    status, output_content, next_query, debug_info = self._process_batch_judgment(
                        question, accumulated_clues, current_contexts, history
                    )
                
                step_info["llm_judgment"] = {
                    "status": status,
                    "clues": output_content,
                    "next_query": next_query
                }
                
                # 填充新增的详情字段
                step_info["context_details"] = {
                    "extracted_snippets_count": len(current_contexts),
                    "strategy": debug_info.get("context_strategy", "Unknown"),
                    "final_prompt": debug_info.get("full_prompt", "")
                }
                step_info["generation_details"] = {
                    "full_response": debug_info.get("llm_response", ""),
                    "response_time_ms": debug_info.get("response_time_ms", 0)
                }

                trace_steps.append(step_info)


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
            "timing": self.phase_logger.get_timings(),
            "trace": trace_steps
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
            "timing": timing,
            "trace": []
        }
