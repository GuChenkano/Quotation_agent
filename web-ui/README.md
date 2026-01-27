# Quotation Agent Web UI

基于 Vue 3 + TypeScript + Element Plus 构建的智能业务助手前端应用。

## 功能特性

- **实时对话**: 与后端 RAG Agent 进行自然语言交互。
- **全链路溯源**: 可视化展示 Agent 的思考过程，包括：
  - 意图识别 (SQL vs RAG)
  - 结构化查询生成的 SQL 语句
  - 迭代式检索过程 (每一轮的检索词、检索结果、LLM 判断)
- **响应式布局**: 左侧对话，右侧溯源，支持自适应调整。

## 技术栈

- **框架**: Vue 3 (Composition API)
- **语言**: TypeScript
- **构建工具**: Vite
- **UI 组件库**: Element Plus
- **样式**: Tailwind CSS
- **状态管理**: Pinia
- **网络请求**: Axios

## 快速开始

### 1. 环境准备
确保已安装 Node.js (建议 v18+) 和 npm。

### 2. 安装依赖
```bash
cd web-ui
npm install
```

### 3. 启动开发服务器
```bash
npm run dev
```
应用将运行在 `http://localhost:5173`。

### 4. 构建生产版本
```bash
npm run build
```

## 后端连接

前端通过 Vite 代理连接后端 API。默认配置如下 (`vite.config.ts`):
```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000', // 后端地址
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, '')
  }
}
```
请确保后端服务 (`api.py`) 已启动并在 8000 端口监听。

## 目录结构

- `src/api`: API 接口封装
- `src/components`: 业务组件 (ChatPanel, TracePanel)
- `src/stores`: Pinia 状态管理
- `src/App.vue`: 根组件与布局
