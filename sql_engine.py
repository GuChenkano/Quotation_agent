
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
        Text-to-SQL 查询流程
        """
        # Reset timings for this call
        self.phase_logger.timings = {}
        
        # 1. 生成 SQL
        with self.phase_logger.phase("生成SQL"):
            sql_query = self._generate_sql(question, history)
            
        if not sql_query:
            return {"answer": "无法生成有效的SQL查询。", "sql": None}
            
        # 2. 执行 SQL
        try:
            with self.phase_logger.phase("执行SQL"):
                with self.engine.connect() as conn:
                    result = conn.execute(text(sql_query))
                    rows = result.fetchall()
                    # 获取列名
                    keys = result.keys()
                    
                    # 格式化结果
                    result_str = ""
                    if not rows:
                        result_str = "查询结果为空。"
                    else:
                        result_str = f"SQL查询结果:\n"
                        # 简单表格展示
                        result_str += " | ".join(keys) + "\n"
                        result_str += "-" * 20 + "\n"
                        for row in rows:
                            result_str += " | ".join([str(x) for x in row]) + "\n"
                        
            # 3. 生成自然语言回答
            with self.phase_logger.phase("生成回答"):
                final_answer = self._generate_answer(question, sql_query, result_str)
                
            return {"answer": final_answer, "sql": sql_query, "raw_result": result_str}
            
        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return {"answer": f"SQL执行出错: {e}", "sql": sql_query}

    def _generate_sql(self, question: str, history: str = "") -> str:
        prompt = f"""
你是一个智能SQL生成专家。你的任务是根据用户的自然语言问题，结合表结构信息，生成准确的SQLite查询语句。

当前场景数据表信息：
- 表名: {self.table_name}
- 可用列名 (Schema): {self.columns}

[历史对话]
{history if history else "无"}

用户问题: {question}

生成规则：
1. **字段映射**：请仔细分析用户问题中的业务术语，并将其映射到最匹配的数据库列名。例如，用户说"部门"可能对应 `dept_name` 或 `department`，"产品"可能对应 `prod_name`。
2. **查询策略**：
   - **明细查询**：如果用户询问"哪些"、"谁"、"列出"、"详细信息"或特定属性（如"价格大于100的订单"），请**查询具体的列**（选择最能代表实体信息的列，如姓名、名称、ID等），不要使用 COUNT(*)。
   - **统计查询**：仅当用户明确只询问"数量"、"多少个"（如"有多少人"、"总销量是多少"）且不需要具体名单时，才使用 COUNT(*) 或 SUM() 等聚合函数。
   - **混合查询**：如果用户同时询问数量和详情（如"有多少个异常订单，列出来"），请**只查询具体数据列**。后续步骤会负责统计数量。
3. **语法规范**：
   - 仅返回纯文本 SQL 语句，不要使用 Markdown 格式（不要 ```sql）。
   - 使用标准 SQLite 语法。
   - 模糊搜索请使用 `LIKE '%keyword%'`。

SQL语句:
"""
        response = self.llm.invoke(prompt)
        sql = response.content.strip()
        # 清理可能存在的markdown标记
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql

    def _generate_answer(self, question: str, sql: str, result_str: str) -> str:
        prompt = Prompts.SQL_ANSWER.format(
            question=question,
            sql=sql,
            result_str=result_str
        )
        return self.llm.invoke(prompt).content
