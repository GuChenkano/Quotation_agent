from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
import time
from contextlib import asynccontextmanager

from agent import RAGAgent
from logger_config import LOG_FORMAT

# 配置日志
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# 全局 Agent 变量
rag_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 初始化 Agent
    global rag_agent
    logger.info("正在初始化 RAG Agent...")
    try:
        rag_agent = RAGAgent()
        logger.info("RAG Agent 初始化完成")
    except Exception as e:
        logger.error(f"RAG Agent 初始化失败: {e}")
        raise e
    yield
    # Shutdown: 清理资源 (如果需要)
    logger.info("Shutting down RAG Agent API")

app = FastAPI(title="Quotation Agent API", version="1.0", lifespan=lifespan)

# --- 请求/响应模型 ---

class QueryRequest(BaseModel):
    question: str
    session_id: str = "default_web"

class SourceItem(BaseModel):
    chunk_id: str
    content: str

class TraceLogItem(BaseModel):
    step: str
    details: Dict[str, Any] = {}
    strategy: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    sql_query: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None
    raw_result: Optional[Any] = None
    trace_log: List[TraceLogItem] = [] # 新增 Trace Log 字段

# --- 接口定义 ---

@app.get("/health")
async def health_check():
    if rag_agent:
        return {"status": "ok", "agent": "ready"}
    return {"status": "initializing"}

@app.post("/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest):
    if not rag_agent:
        raise HTTPException(status_code=503, detail="Agent is still initializing")
    
    logger.info(f"收到请求: session_id={request.session_id}, question={request.question}")
    
    try:
        # 调用 Agent 的核心 chat 方法
        result = rag_agent.chat(request.question, session_id=request.session_id)
        
        # 构造响应
        response = QueryResponse(
            answer=result.get("answer", "No answer generated"),
            sources=result.get("sources", []),
            timing=result.get("timing", {}),
            sql_query=result.get("sql_query"),
            evaluation=result.get("evaluation"),
            raw_result=str(result.get("raw_result")) if result.get("raw_result") else None,
            trace_log=result.get("trace_log", [])
        )
        return response
        
    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 开发环境下直接运行
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
