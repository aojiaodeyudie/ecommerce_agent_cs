# 🛒 电商多商家智能客服系统

基于 **LangChain v1 (create_agent + 中间件)** 的 ReAct 智能客服系统,支持**智能客服 + 6 家独立商家店铺**,每个商家拥有专属商品库、知识库与客服身份。包含消费者端聊天界面与运营端管理后台(人工坐席台 / 数据看板 / badcase 分析)。

## ✨ 核心特性

- **多商家架构**:智能客服(平台全店兜底)+ 星辉数码 / 蓝鲸家电 / 云端生活 / 绿野家居 / 鲜橙生鲜 / 悦读书香 6 家店铺,各自独立会话、商品、知识域与客服人设
- **意图路由省钱**:投诉词直接转人工建工单、FAQ 库零成本直答、其余走 Agent(工具 + RAG),三级路由控制成本
- **ReAct Agent**:LangChain v1 `create_agent` + 中间件,实现槽位追问(缺什么问什么)、写操作二次确认、商家身份动态注入
- **分域 RAG 知识库**:7 个独立 Chroma collection(平台 + 6 商家),约 430 条知识问答;商家域未命中自动回退平台兜底
- **运营闭环**:人工坐席台(工单分页/搜索/坐席回复/差评跟进)、数据看板(意图分布/差评统计/星级评价)、badcase 分析(FAQ 盲区一键入库)
- **完整交互**:SSE 流式输出、Markdown 渲染、满意度星级评价(1-5 星 + 是否解决 + 问题描述)、图片/表情发送、多用户切换

## 🏗️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Vite + TypeScript + Ant Design 5 |
| API | FastAPI + sse-starlette(SSE 流式) |
| Agent | LangChain v1 `create_agent` + 中间件 |
| 模型 | 通义千问 qwen3-max(对话)+ text-embedding-v4(向量) |
| 向量库 | Chroma(分域多 collection) |
| 业务库 | SQLite(商品/订单/物流/工单/会话/FAQ) |
| 部署 | Docker / nginx / iframe 网页挂件 |

## 📁 目录结构

```
├── agent/          # Agent 层(react_agent + 中间件)
├── api/            # FastAPI 层(routers: chat/business/ops)
├── ecommerce/      # 电商模块(db/tools/slots/router/intent/faq/chat_service...)
├── rag/            # RAG 层(rag_service + vector_stores 分域)
├── model/          # 模型工厂(惰性单例)
├── frontend/       # React 前端(消费者端 + 运营端)
├── config/         # YAML 配置(chroma 7 域 / ecommerce 路由规则)
├── prompts/        # 系统提示词(平台 + 各场景 Agent)
├── data/kb/        # 知识源文档(7 个域,随仓库分发)
├── tests/          # pytest 测试集(46 项)
└── utils/          # 工具层(配置/日志/路径/提示词加载)
```

## 🚀 快速开始

### 环境要求
- Python 3.10+(开发环境 3.12)
- Node.js 18+
- 阿里云百炼 API Key(https://bailian.console.aliyun.com)

### 1. 克隆并安装

```bash
git clone https://github.com/aojiaodeyudie/ecommerce_agent_cs.git
cd ecommerce_agent_cs

# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..
```

### 2. 配置 API Key

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
# 编辑 .env,填入 DASHSCOPE_API_KEY=你的key
```

> 也可以设置系统环境变量 `DASHSCOPE_API_KEY`,二选一即可。

### 3. 启动

```bash
# 终端 1:后端 API
uvicorn api.main:app --port 8000

# 终端 2:前端(开发模式)
cd frontend && npm run dev
```

浏览器打开 **http://localhost:5173**(前端自动代理 `/api` 到 8000)。

> 生产模式:先 `cd frontend && npm run build`,再启动 uvicorn,http://localhost:8000 单服务托管前后端。

### 4. (可选)重建知识库

知识库已随仓库分发(`data/chroma_db/`),无需重建即可使用。如需重建:

```bash
python -m rag.vector_stores ai        # 平台域
python -m rag.vector_stores shop_b    # 各商家域(shop_a~shop_f)...按需
```

## 🧪 测试

```bash
# 冒烟测试(无需 API key)
python test_ecommerce.py

# pytest 测试集(无需 API key)
pytest tests/ -v
```

## 🖥️ 使用说明

- **消费者端**:左侧切换对话对象(智能客服 / 6 家商家),支持 SSE 流式对话、快捷用语、图片/表情发送、星级评价本次服务、多用户切换
- **运营端**:人工坐席台(工单处理/坐席回复/1-3 星差评跟进)、数据看板(意图分布/差评统计)、badcase 分析(FAQ 盲区一键入库)

## 🐳 Docker 部署

```bash
docker compose up -d --build
# 访问 http://服务器IP:8000(API + 前端)
# 首次启动后需在容器内灌库(按域执行,数据已随仓库分发时可跳过):
docker compose exec customer-service python -m rag.vector_stores ai
docker compose exec customer-service python -m rag.vector_stores shop_b
```

## 📄 文档

- [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md):完整文件结构说明
- [`DEPLOY.md`](DEPLOY.md):部署指南(本地/Docker/nginx/网页嵌入)

