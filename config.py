
# --- 全局配置参数 (Global Configuration) ---
# LM Studio 连接配置
LM_STUDIO_API_BASE = "http://192.168.30.190:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"

# 模型配置
EMBEDDING_MODEL_NAME = "text-embedding-bge-m3"
CHAT_MODEL_NAME = "qwen/qwen3-4b-2507"

# 路径配置
DB_PERSIST_DIR = r"D:\DM\LangChain\联络名单-Agent\Quotation_agent\chroma_db"
MASTER_JSON_PATH = r"D:\DM\LangChain\联络名单-Agent\Quotation_agent\json_save\unified_data.json"
JSON_DATA_PATH = MASTER_JSON_PATH


# RAG 检索参数
RETRIEVAL_K = 10 #模型上下文限制为40000
CHUNK_OVERLAP = 0 # 这里的Chunk是基于Excel行的，没有重叠

# 评估配置
ENABLE_RAGAS_EVALUATION = False # 是否开启 Ragas 评估，设为 False 可跳过评估步骤以节省时间和避免超时

# 默认场景配置 
DEFAULT_SCENARIO = "企业联络名单"

# --- 统一 Prompt 管理 ---
class Prompts:
    # 1. 意图识别
    INTENT_CLASSIFICATION = """
你是一个智能意图识别助手。你的任务是根据用户问题的语义，判断用户问题的类型。

用户问题: {question}

类型定义：
1. SQL (结构化查询): 涉及对结构化数据中字段的统计、计算、筛选或属性查询。
   - 特征：包含“数量/总和/平均/最大值/最小值”“大于/小于/等于”“列出...详情”“XX的YY是什么”等明确操作指令。
   - 示例：“{scenario}中共有多少条记录？”“统计各分类的数量”“列出数值高于阈值的条目”“ID为1001的记录中‘状态’字段值是什么”。

2. RAG (知识检索): 涉及对文档、说明、流程、定义等非结构化内容的理解与提取。
   - 特征：包含“是什么/如何/为什么/介绍一下/背景/步骤/依据”等语义理解类提问。
   - 示例：“该流程的操作规范是什么？”“此错误代码的处理依据？”“某配置项的作用说明”。

请仅返回：SQL 或 RAG（无标点、无解释）
"""

    # 2. SQL 生成
    SQL_GENERATION = """
你是一个SQL生成专家。根据用户问题与表结构，生成标准SQLite查询。

当前场景数据表信息：
- 表名: {table_name}
- 可用列名 (Schema): {columns}

[历史对话]
{history}

用户问题: {question}

生成规则：
1. 字段映射：将用户术语映射至最匹配的列名（如“分类”→`category`，“项目”→`item_name`）。
2. 查询策略：
   - 明细查询：当问题含“列出/哪些/详情/属性值”时，SELECT具体字段（避免COUNT）。
   - 统计查询：仅当明确问“总数/合计/平均值”且无需明细时，使用聚合函数。
   - 混合查询：优先返回明细数据，数量统计由后续环节处理。
3. 语法规范：
   - 仅返回纯文本 SQL 语句，不要使用 Markdown 格式（不要 ```sql）。
   - 使用标准 SQLite 语法。
   - 模糊搜索请使用 `LIKE '%keyword%'`。

SQL语句:
"""

    # 3. SQL 结果回答
    SQL_ANSWER = """
用户问题: {question}
执行的SQL: {sql}
查询结果:
{result_str}

请根据上述查询结果，以自然、流畅的语言回答用户问题。
1. **数据解读**：直接基于查询结果回答。如果结果是列表且用户问数量，请手动统计行数并回答（例如"共找到 N 条记录..."）。
2. **信息展示**：默认制表列出详情，请条理清晰地列出结果中的关键信息。除非用户指明只需要结果数量，否则请展示所有相关数据。
3. **空结果**：友好提示“未找到符合条件的数据”。
4. **通用性**：请根据实际数据内容回答，使用“记录/条目/数量”等中性词表述。
"""

    # 4. RAG 检索判断 - System
    RAG_JUDGMENT_SYSTEM = """
你是一个智能检索助手。你的任务是判断提供的参考资料是否包含回答用户问题的完整信息。
严格遵守以下规则：
1. 禁止幻觉：未在资料中找到确切关键词、标识符、数值或描述时，绝不猜测或关联相似内容。
2. 多轮检索：资料不足时优先返回 SEARCH_MORE 并提供新线索；仅当多次尝试无果后才 GIVE_UP。
3. 精确匹配：对ID、编号、代码、专有名词等关键实体，必须完全一致。
"""

    # 5. RAG 检索判断 - User
    RAG_JUDGMENT_USER = """
[历史对话]
{history}

[用户问题]
{question}

[已累积的线索]
{accumulated_clues}

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
- NEXT_QUERY 需具体、避免重复已搜词
- 禁止编造答案或强行关联
"""

    # 6. RAG 最终总结
    RAG_SUMMARY = """
[历史对话]
{history}

用户问题：{question}
已收集的线索：
{clues}

请基于上述线索，尝试回答问题。
重要原则：
1. 如果根据线索可以回答问题，请提供直接的答案。
2. 如果线索不足以回答，或者找不到相关信息，请严格只回答一句："根据知识库内容无法提供回答"，不要包含"已知相关信息"、"结论"或其他解释。
"""

    # 7. Excel 表头识别
    HEADER_IDENTIFICATION = """
你是一个专业的Excel数据分析助手。请分析以下Excel工作表的前20行数据，找出包含列名（表头）的那一行。
通常表头行包含描述性的字段名称（如"姓名"、"电话"、"地址"等）。

数据预览：
{preview_text}

请直接返回表头所在的行号（从0开始计数）。
只返回一个数字，不要包含任何其他文字或解释。
如果无法确定，请返回 0。
"""

    # 8. 字段智能映射分析
    COLUMN_MATCHING = """
你是一个通用的数据库Schema语义映射引擎。你的核心任务是分析自然语言查询中的“筛选条件实体”，并将其映射到数据库Schema中最可能对应的“列名”。

[上下文信息]
- 数据表名: {table_name}
- 完整列名列表: {columns}
- 用户查询: {question}

[执行逻辑]
1. **实体提取**：从用户查询中识别出作为“筛选条件”或“查询对象”的关键名词或短语（忽略停用词和通用动词）。
2. **语义映射**：在列名列表中寻找与提取出的实体在语义上高度相关、存在包含关系或同义关系的字段。
   - 优先匹配：完全匹配 > 同义词/缩写匹配 > 语义相关 > 模糊匹配。
   - 跨域适应：请基于列名的字面意义和通用语义进行推理，不要局限于特定行业术语。
3. **理由说明**：简要说明匹配的依据。

[输出规范]
- 必须且仅返回一个纯 JSON 对象。
- 格式：{{"candidates": ["列名1", "列名2"], "reason": "匹配理由"}}
- 严禁包含 Markdown 格式（如 ```json）、解释性文字或换行符。
- 如果用户查询中未包含任何具体的筛选实体，或无法找到任何相关列名，请返回空列表 []。

[示例]
Input: "查找所有状态为活跃的用户" (Columns: ["user_status", "name", "id"])
Output: {{"candidates": ["user_status"], "reason": "用户提到的'状态'语义映射到字段 'user_status'"}}

Input: "Show me details about Project Alpha" (Columns: ["proj_name", "description", "manager"])
Output: {{"candidates": ["proj_name", "description"], "reason": "Project Alpha implies filtering by project name"}}

Input: "统计总数" (无明确筛选实体)
Output: {{"candidates": [], "reason": "无明确筛选实体"}}
"""
