# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在处理本代码仓库中的代码时提供指导。

## 项目概述

Quotation Agent 是一个智能业务助手，结合 SQL 与 RAG（检索增强生成）技术，可同时处理结构化与非结构化查询。系统能自动识别用户意图，并将查询路由至相应的引擎。

## 核心架构

**双引擎系统：**
- **SQL 引擎**（`sql_engine.py`）：处理对表格数据的结构化查询
- **RAG 引擎**（`retrieval_engine.py`）：通过迭代检索处理非结构化知识查询
- **意图分类器**（`agent.py`）：基于语义分析对查询进行路由
- **回退机制**：主路径失败时自动按 SQL → RAG → SQL 顺序回退

**核心组件：**
- `agent.py`：主协调器（RAGAgent 类）
- `api.py`：带会话管理的 FastAPI 接口
- `memory.py`：对话历史追踪
- `evaluator.py`：可选的 Ragas 质量评估模块

## 开发命令

### 后端（Python/FastAPI）
```bash
# 启动后端服务
python api.py  # 默认运行于 8000 端口

# 运行测试
python test_api.py                    # API 接口测试
python test_generalization.py         # RAG 评估测试
python test_sql_optimization.py       # SQL 优化测试

# 一键启动（Windows）
start_app.bat  # 同时启动后端和前端
```

### 前端（Vue.js + TypeScript）
```bash
cd web-ui

# 安装依赖
npm install

# 开发服务器
npm run dev    # 默认运行于 5173 端口

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

## 数据流

1. 用户通过 Web 界面提交问题
2. 意图分类器判断使用 SQL 或 RAG 路径
3.
   - **SQL 路径**：生成 SQL → 在 SQLite 上执行 → 格式化响应
   - **RAG 路径**：迭代检索（最多 3 轮）→ 生成答案
4. 完整执行轨迹记录并发送至前端
5. 若主路径失败，则触发回退机制

## 关键配置

**模型设置**（`config.py`）：
- 端点：`http://192.168.30.190:1234/v1`（LM Studio）
- 嵌入模型：`text-embedding-bge-m3`
- 聊天模型：`qwen/qwen3-4b-2507`

**数据源：**
- 主数据：`json_save/unified_data.json`（内存中的 SQLite 表）
- 向量数据库：`chroma_db/` 目录（ChromaDB 持久化存储）

**提示词（Prompts）**：所有提示词均位于 `config.py` 中的 `Prompts` 类（中文）

## 测试方法

- 使用 TestClient 进行 API 测试（参见 `test_api.py`）
- 通过 `session_id` 参数实现会话管理
- 通过 `ENABLE_RAGAS_EVALUATION` 标志启用可选评估

## 常见开发任务

**新增 SQL 查询：**
- 在 SQL 生成提示词中定义表结构映射
- 使用多种中英文别名进行测试

**修改 RAG 行为：**
- 调整 `RETRIEVAL_K` 参数
- 修改 `retrieval_engine.py` 中的迭代检索逻辑

**前端修改：**
- 主聊天界面：`web-ui/src/components/ChatPanel.vue`
- 执行轨迹展示：`web-ui/src/components/TracePanel.vue`
- API 客户端：`web-ui/src/api/agent.ts`

## 重要说明

- 所有提示词均为中文——修改时请保持中文提示词
- SQL 查询使用 SQLite 语法（内存数据库）
- 通过基于 UUID 的会话 ID 实现会话隔离
- 轨迹日志包含完整的执行流程，便于调试
- 前端通过 Vite 代理连接后端（8000 端口）