
import json
import logging
import pandas as pd
from typing import Dict, Any
from pathlib import Path
from sqlalchemy import create_engine, text

from config import Prompts
from logger_config import PhaseLogger

logger = logging.getLogger(__name__)

class StructuredQueryEngine:
    """
    处理结构化查询（Text-to-SQL）
    """
    def __init__(self, llm, json_path: str):
        self.phase_logger = PhaseLogger("StructuredQueryEngine")
        self.llm = llm
        self.json_path = json_path
        
        with self.phase_logger.phase("引擎初始化"):
            self.engine = create_engine('sqlite:///:memory:') # 使用内存数据库
            # 动态设置表名，默认为文件名（去除非法字符）
            safe_name = Path(json_path).stem.replace(" ", "_").replace("-", "_")
            self.table_name = safe_name if safe_name else "main_table"
            self._load_data()

    def reload_data(self, json_path: str = None):
        """重新加载数据"""
        with self.phase_logger.phase("数据重载"):
            if json_path:
                self.json_path = json_path
                # 更新表名
                safe_name = Path(json_path).stem.replace(" ", "_").replace("-", "_")
                self.table_name = safe_name if safe_name else "main_table"
            self._load_data()

    def _load_data(self):
        """将JSON数据加载到SQLite"""
        if not Path(self.json_path).exists():
            logger.error(f"JSON文件不存在: {self.json_path}")
            return

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            all_rows = []
            
            # 智能识别数据结构
            if isinstance(raw_data, list) and len(raw_data) > 0:
                first_item = raw_data[0]
                # 检查是否为 RAG 系统的分块格式 [{"chunk-id": {"content": [...]}}]
                is_chunk_format = False
                if isinstance(first_item, dict):
                    # 简单启发式：检查是否有 chunk-id 风格的键或 content 字段
                    keys = list(first_item.keys())
                    if keys and isinstance(first_item[keys[0]], dict) and "content" in first_item[keys[0]]:
                        is_chunk_format = True
                
                if is_chunk_format:
                    # 处理嵌套结构
                    for entry in raw_data:
                        for chunk_data in entry.values():
                            content_list = chunk_data.get("content", [])
                            all_rows.extend(content_list)
                else:
                    # 处理扁平 List[Dict] 结构
                    all_rows = raw_data
            else:
                logger.warning("JSON数据格式不识别或为空")
                return
            
            if not all_rows:
                logger.warning("未提取到任何数据行")
                return

            df = pd.DataFrame(all_rows)
            # 数据清洗：将空字符串和NaN都转为None
            df = df.replace(r'^\s*$', None, regex=True)
            df = df.where(pd.notnull(df), None)
            
            # 列名清洗：将特殊字符替换为下划线，避免SQL语法错误
            df.columns = [str(c).replace('/', '_').replace(' ', '_').replace('-', '_').strip() for c in df.columns]
            
            # 写入SQLite
            df.to_sql(self.table_name, self.engine, index=False, if_exists='replace')
            logger.info(f"成功加载 {len(df)} 行数据到结构化数据库表 '{self.table_name}'")
            
            # 获取列名供Prompt使用
            self.columns = df.columns.tolist()
            logger.info(f"表列名: {self.columns}")
            
        except Exception as e:
            logger.error(f"加载结构化数据失败: {e}")

    def query(self, question: str, history: str = "") -> Dict[str, Any]:
        """
        Text-to-SQL 查询流程（优化版：支持智能字段匹配与试探性检索）
        """
        # Reset timings for this call
        self.phase_logger.timings = {}
        
        # 0. 调试信息：打印所有可用字段
        logger.info(f"当前数据表 '{self.table_name}' 的所有列名: {self.columns}")

        # 1. 字段匹配分析
        candidate_columns = []
        with self.phase_logger.phase("字段匹配分析"):
            try:
                candidate_columns = self._analyze_columns(question)
                logger.info(f"LLM 推荐的候选字段: {candidate_columns}")
            except Exception as e:
                logger.warning(f"字段分析失败: {e}")
        
        # 如果没有推荐字段，默认执行一次无Hint的生成
        if not candidate_columns:
            candidate_columns = [None]
        else:
            # 确保候选字段是唯一的，并且在 self.columns 中（可选，也可以允许模糊匹配交由SQL处理）
            # 这里我们只去重
            candidate_columns = list(dict.fromkeys(candidate_columns))

        final_sql = None
        final_result_str = None
        final_row_count = 0
        final_keys = []
        last_error = None
        sql_attempts = [] # 记录所有尝试的详细信息
        
        # 2. 多字段试探性检索
        for attempt, col_hint in enumerate(candidate_columns):
            hint_msg = ""
            if col_hint:
                hint_msg = f"注意：问题中的实体可能对应数据库表中的字段 `{col_hint}`，请优先使用该字段进行查询。"
                
            logger.info(f"Attempt {attempt+1}: Generating SQL with hint column '{col_hint}'...")
            
            attempt_info = {
                "attempt": attempt + 1,
                "hint_column": col_hint,
                "sql": None,
                "result": None,
                "status": "FAILED"
            }
            
            with self.phase_logger.phase(f"生成SQL_尝试{attempt+1}"):
                sql_query = self._generate_sql(question, history, hint=hint_msg)
                attempt_info["sql"] = sql_query
            
            if not sql_query:
                sql_attempts.append(attempt_info)
                continue
                
            # 执行 SQL
            try:
                with self.phase_logger.phase(f"执行SQL_尝试{attempt+1}"):
                    with self.engine.connect() as conn:
                        result = conn.execute(text(sql_query))
                        rows = result.fetchall()
                        keys = result.keys()
                        
                        # 结果评估机制
                        if rows:
                            # 成功且有数据
                            result_str = f"SQL查询结果:\n"
                            result_str += " | ".join(keys) + "\n"
                            result_str += "-" * 20 + "\n"
                            for row in rows:
                                result_str += " | ".join([str(x) for x in row]) + "\n"
                            
                            # 采纳此结果
                            final_sql = sql_query
                            final_result_str = result_str
                            final_row_count = len(rows)
                            final_keys = list(keys)
                            
                            attempt_info["result"] = result_str
                            attempt_info["status"] = "SUCCESS"
                            sql_attempts.append(attempt_info)
                            
                            logger.info(f"SQL 尝试成功 (Hint: {col_hint}): Found {len(rows)} rows.")
                            break # 找到有效结果，停止尝试
                        else:
                            # 结果为空，继续尝试下一个字段
                            logger.info(f"SQL 尝试返回空结果 (Hint: {col_hint}). Trying next candidate...")
                            if final_sql is None: # 保留第一个空结果作为保底
                                final_sql = sql_query
                                final_result_str = "查询结果为空。"
                                final_row_count = 0
                                final_keys = list(keys)
                            
                            attempt_info["result"] = "Empty Result"
                            attempt_info["status"] = "EMPTY"
                            sql_attempts.append(attempt_info)
                            
            except Exception as e:
                logger.warning(f"SQL 尝试执行报错 (Hint: {col_hint}): {e}")
                last_error = e
                attempt_info["error"] = str(e)
                sql_attempts.append(attempt_info)
                # 继续尝试下一个
        
        # 3. 最终结果处理
        if not final_sql:
            return {
                "answer": f"无法生成有效的SQL查询或所有尝试均失败。Last Error: {last_error}", 
                "sql": None,
                "raw_result": None,
                "sql_attempts": sql_attempts
            }
            
        if not final_result_str:
            final_result_str = "查询结果为空。"

        # 4. 生成自然语言回答
        with self.phase_logger.phase("生成回答"):
            final_answer = self._generate_answer(question, final_sql, final_result_str, final_row_count, final_keys)
            
        return {
            "answer": final_answer, 
            "sql": final_sql, 
            "raw_result": final_result_str,
            "sql_attempts": sql_attempts # 返回详细尝试记录供 Trace 使用
        }

    def _analyze_columns(self, question: str) -> list:
        """调用 LLM 分析问题并返回候选字段列表"""
        logger.info(f"[StructuredQueryEngine] - LLM字段匹配输入: 问题=\"{question}\", 表=\"{self.table_name}\", 列名={self.columns}")
        
        prompt = Prompts.COLUMN_MATCHING.format(
            table_name=self.table_name,
            columns=self.columns,
            question=question
        )
        response = self.llm.invoke(prompt)
        content = response.content.strip()
        # 清理可能的 markdown 格式
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            result = json.loads(content)
            candidates = []
            reason = "无"
            
            if isinstance(result, dict):
                candidates = result.get("candidates", [])
                reason = result.get("reason", "无")
            elif isinstance(result, list):
                # 兼容旧格式
                candidates = result
                reason = "兼容旧格式直接返回列表"
            
            # 截断理由如果太长（虽然不太可能，但保持一致性）
            log_reason = reason[:500] + "[...截断]" if len(reason) > 500 else reason
            logger.info(f"[StructuredQueryEngine] - LLM字段匹配输出: 候选字段={candidates}, 理由=\"{log_reason}\"")
            
            return candidates
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse column candidates JSON: {content}")
            return []

    def _generate_sql(self, question: str, history: str = "", hint: str = "") -> str:
        prompt = Prompts.SQL_GENERATION.format(
            table_name=self.table_name,
            columns=self.columns,
            history=history if history else "无",
            question=question,
            hint=hint
        )
        
        # 记录输入
        logger.info(f"[StructuredQueryEngine] - LLM SQL生成输入: 问题=\"{question}\", 候选字段提示=\"{hint}\", 表结构={self.columns}")
        
        response = self.llm.invoke(prompt)
        sql = response.content.strip()
        # 清理可能存在的markdown标记
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        # 记录输出
        log_sql = sql[:500] + "[...截断]" if len(sql) > 500 else sql
        logger.info(f"[StructuredQueryEngine] - LLM生成的SQL查询语句如下: {log_sql}")
        
        return sql

    def _generate_answer(self, question: str, sql: str, result_str: str, row_count: int = 0, key_fields: list = None) -> str:
        # 记录输入
        key_fields_str = ", ".join(str(k) for k in key_fields) if key_fields else "无"
        logger.info(f"[StructuredQueryEngine] - LLM回答生成输入: 问题=\"{question}\", SQL结果摘要=\"共{row_count}行，包含字段: {key_fields_str}\"")
        
        prompt = Prompts.SQL_ANSWER.format(
            question=question,
            sql=sql,
            result_str=result_str
        )
        content = self.llm.invoke(prompt).content
        
        # 记录输出
        log_content = content[:500] + "[...截断]" if len(content) > 500 else content
        logger.info(f"[StructuredQueryEngine] - LLM生成的回答: \"{log_content}\"")
        
        return content
