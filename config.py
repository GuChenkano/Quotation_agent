
# --- 全局配置参数 (Global Configuration) ---
# LM Studio 连接配置
LM_STUDIO_API_BASE = "http://192.168.30.190:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"

# 模型配置
EMBEDDING_MODEL_NAME = "text-embedding-bge-m3"
CHAT_MODEL_NAME = "qwen/qwen3-4b-2507"

# 路径配置
DB_PERSIST_DIR = r"D:\DM\LangChain\联络名单-Agent\chroma_db"
JSON_DATA_PATH = r"D:\DM\LangChain\联络名单-Agent\json_save\报价汇总表2025_报价汇总表2025.json"

# RAG 检索参数
RETRIEVAL_K = 10 #模型上下文限制为40000
CHUNK_OVERLAP = 0 # 这里的Chunk是基于Excel行的，没有重叠

# 评估配置
ENABLE_RAGAS_EVALUATION = False # 是否开启 Ragas 评估，设为 False 可跳过评估步骤以节省时间和避免超时

# 默认场景配置 
DEFAULT_SCENARIO = "企业联络名单"
