# RAG系统Web测试与调试界面开发任务书

## 项目背景
当前拥有一个功能完整的RAG双引擎后端系统（已在 `agent.py` 中实现），具备智能路由能力，能自动选择RAG或SQL模式，但现在需要开发一个配套的Web测试与调试界面，用于展示系统的完整执行链路。项目环境使用conda activate LangChainV2，向量数据库使用ChromaDB。D:\DM\LangChain\联络名单-Agent\Quotation_agent\chroma_db，chunks数据在D:\DM\LangChain\联络名单-Agent\Quotation_agent\json_save\unified_data.json。

## 当前后端能力（已验证）

### ✅ 后端已实现功能
1. **双引擎智能路由** - 基于意图识别自动选择SQL或RAG模式
2. **完整工作流追踪** - `agent.py` 中的 `chat()` 方法返回详细执行步骤
3. **对话记忆管理** - 支持 `session_id` 维度的多轮对话
4. **错误回退机制** - SQL失败自动切换RAG，反之亦然
5. **多场景支持** - 通过 `config.py` 支持不同业务场景配置

### ❌ 需要补强的后端接口
1. **Web API封装** - 将 `agent.chat()` 封装为RESTful API
2. **执行链路序列化** - 将内部追踪数据转为前端可用的JSON格式
3. **历史对话功能** - 历史对话存储在D:\DM\LangChain\联络名单-Agent\Quotation_agent\json_save\history.json，使用json格式存储，每个对话项包含用户消息、AI回复、执行链路等。

## 前端核心需求

### 1. 双面板布局设计
```
┌─────────────────────────┬─────────────────────────────┐
│  对话历史列表            │  当前对话主窗口             │
│  ┌─────┐                │  ┌───────────────────────┐ │
│  │对话1│                │  │ 用户消息               │ │
│  └─────┘                │  └───────────────────────┘ │
│  ┌─────┐                │  ┌───────────────────────┐ │
│  │对话2│                │  │ AI回复                 │ │
│  └─────┘                │  └───────────────────────┘ │
│                         │                            │
│                         │  【调试/溯源面板】          │
│                         │  ▼ 可折叠                  │
│                         │  ┌───────────────────────┐ │
│                         │  │ 时间轴视图             │ │
│                         │  │ • 意图识别             │ │
│                         │  │ • LLM调用              │ │
│                         │  │ • 检索详情             │ │
│                         │  │ • 执行结果             │ │
│                         │  └───────────────────────┘ │
└─────────────────────────┴─────────────────────────────┘
```

### 2. 调试面板详细需求

#### 时间轴节点设计
1. **意图识别节点**
   - 显示判断结果：`SQL模式` / `RAG模式`
   - 显示判断置信度和理由
   - 耗时统计（ms）

2. **LLM调用节点**
   - 可折叠的代码块展示完整Prompt
   - System Prompt 和 User Prompt 分开展示
   - 支持 JSON/SQL 语法高亮（使用 Prism.js 或 Shiki）
   - 显示 LLM 思考过程（如果有的话）

3. **检索详情节点**
   - **SQL模式**：
     - 展示生成的 SQL 语句（带语法高亮）
     - 展示查询结果表格（限制前10行）
     - 显示执行耗时和影响的行数
   - **RAG模式**：
     - 展示 Top-K 文档列表（K值可配置）
     - 每个文档显示：
       - 内容片段（限制200字符）
       - 来源文档路径
       - 相似度分数（百分比）
       - Chunk ID

4. **最终结果节点**
   - 展示最终答案
   - 显示总耗时
   - 显示是否触发了回退机制

### 3. 技术实现规范

#### 前端技术栈建议
```typescript
// 推荐技术组合
{
  "framework": "Vue 3 + TypeScript",
  "UI_Library": "Element Plus",
  "HTTP_Client": "Axios",
  "SSE_Client": "@microsoft/fetch-event-source",
  "Code_Highlighter": "Prism.js",
  "Timeline_Component": "Element Plus Timeline",
  "Table_Component": "Element Plus Table",
  "Layout": "Element Plus Container + Flex"
}
```

#### 关键组件拆分
```
src/
├── components/
│   ├── ChatInterface.vue          # 主对话界面
│   ├── DebugPanel.vue             # 调试面板（包含时间轴）
│   ├── MessageBubble.vue          # 消息气泡组件
│   ├── CodeBlock.vue              # 代码高亮组件
│   ├── SqlResultTable.vue         # SQL结果表格
│   ├── RagDocuments.vue           # RAG文档列表
│   └── TimelineNode.vue           # 时间轴节点
├── services/
│   ├── api.ts                     # API接口定义
│   └── sse.ts                     # SSE流处理
├── types/
│   └── chat.ts                    # TypeScript类型定义
└── utils/
    ├── highlight.ts               # 代码高亮工具
    └── formatters.ts              # 数据格式化
```

#### API接口定义（需要先实现后端）
```typescript
// 请求类型
interface ChatRequest {
  message: string;
  session_id?: string;
}

// 响应类型（流式）
interface ChatStreamEvent {
  type: 'start' | 'intent' | 'execute' | 'thinking' | 'answer' | 'debug' | 'end';
  data: {
    // 根据type不同，data结构不同
    intent?: {
      mode: 'sql' | 'rag';
      confidence: number;
      reason: string;
    };
    sql?: {
      query: string;
      results: any[];
      execution_time: number;
    };
    rag?: {
      documents: Array<{
        content: string;
        source: string;
        score: number;
        chunk_id: string;
      }>;
    };
    thinking?: string;
    answer?: string;
    debug?: ExecutionStep[];
  };
  timestamp: number;
}

interface ExecutionStep {
  id: string;
  type: 'intent' | 'llm' | 'sql' | 'rag' | 'fallback';
  status: 'pending' | 'running' | 'success' | 'failed';
  duration: number;
  input?: any;
  output?: any;
  error?: string;
}
```

### 4. 后端API开发（优先级最高）

#### 需要先实现的后端接口
```python
# FastAPI 示例（需要新增 fastapi_service.py）
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncGenerator

app = FastAPI()

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """处理聊天请求，返回 SSE 流式响应"""
    # 1. 调用现有 agent.chat() 方法
    # 2. 将内部步骤序列化为标准格式
    # 3. 通过 SSE 流式发送给前端
    pass

@app.get("/api/sessions")
async def list_sessions():
    """获取所有对话历史"""
    # 从 memory.py 中加载所有 session
    pass

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取特定对话的完整历史"""
    # 返回带调试信息的完整对话
    pass
```

### 5. 开发优先级

#### 第一阶段（MVP）
1. ✅ 实现基础的 FastAPI 接口
2. ✅ 创建简单的前端界面（仅对话功能）
3. ✅ 支持 SSE 流式响应
4. ✅ 基本的调试信息显示

#### 第二阶段（核心功能）
1. ⏳ 完善的时间轴调试面板
2. ⏳ 代码语法高亮
3. ⏳ SQL结果表格展示
4. ⏳ RAG文档列表展示

#### 第三阶段（优化体验）
1. ⏳ 历史对话管理
2. ⏳ 响应式布局优化
3. ⏳ 性能优化
4. ⏳ 错误处理和重试机制

### 6. 关键注意事项

1. **流式响应处理**
   - SSE事件需要按顺序处理，保持时间轴正确性
   - 大SQL结果集需要分页或限制显示
   - RAG文档过多时使用虚拟滚动

2. **错误处理**
   - 后端执行失败时，前端要展示详细的错误信息
   - 网络断开时显示重连按钮
   - 前端添加请求超时处理

3. **性能优化**
   - 调试面板默认折叠，按需渲染
   - 长对话历史使用虚拟列表
   - 代码高亮使用异步加载

### 7. 成功标准

1. 用户可以清晰看到每个问题的处理流程
2. 调试信息完整展示所有中间步骤
3. 界面响应流畅，支持快速切换历史对话
4. 代码高亮和表格展示清晰易读
5. 移动端适配基本可用

## 下一步行动

### 立即需要做的：
1. 创建 `requirements_web.txt` 添加 FastAPI 依赖
2. 新建 `fastapi_service.py` 实现 Web API
3. 创建前端项目目录 `web_ui/`
4. 使用 Vue CLI 或 Vite 初始化前端项目

### 验证检查点：
1. 后端 `/api/chat` 能正常调用 `agent.chat()`
2. 前端能接收 SSE 流式响应
3. 调试面板的每个节点都能正确显示数据
4. 语法高亮对 SQL 和 JSON 生效
