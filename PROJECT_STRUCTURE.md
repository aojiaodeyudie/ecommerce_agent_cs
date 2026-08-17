# 项目文件结构说明（Project Structure）

> 📌 **本文档是项目的"文件地图"**：逐一说明每个模块、每个文件的职责。
> **维护约定**：每当项目新增/修改/删除文件，本文档必须同步更新（新增文件 → 补进对应模块表格；删除文件 → 移除条目；修改职责 → 更新说明）。

---

## 1. 项目概览

**电商智能客服**（由"扫地机器人智能客服"教学项目改造而来）：基于 LangChain v1（`create_agent` + 中间件）的 ReAct Agent，提供售前咨询 / 售中订单 / 售后处理全流程客服能力。阶段二引入**意图路由**：投诉直接转人工、高频问题 FAQ 直答（零 LLM 成本）、其余走 Agent（工具 + 分域 RAG 检索）。

- **入口**：`frontend/`（React 前端）+ `api/`（FastAPI，生产时单服务托管前后端）
- **模型**：通义千问 qwen3-max（对话）+ text-embedding-v4（向量），走阿里云百炼 DashScope
- **向量库**：Chroma（`data/chroma_db`，分域多 collection）
- **业务库**：SQLite（`data/ecommerce.db`）
- **路由**：`ecommerce/router.py`（escalate / faq / agent 三分支）

---

## 2. 目录结构总览

```
Agent开发/
├── requirements.txt            # 依赖清单
├── test_ecommerce.py           # 冒烟测试脚本（无 key）
├── DEPLOY.md                   # 部署指南（本地/Docker/nginx/嵌入）
├── Dockerfile                  # 容器镜像（多阶段：前端构建 + 后端）
├── docker-compose.yml          # 容器编排
├── .dockerignore               # 构建排除项
├── .env.example                # 环境变量模板（DASHSCOPE_API_KEY）
├── embed.html                  # 网页挂件示例（iframe 嵌入 React 前端）
├── md5.text                    # 知识库文件 MD5 去重记录（默认域）
├── agent/                      # Agent 层
│   ├── react_agent.py          # ReAct Agent 构建与流式执行（多轮上下文）
│   └── tools/
│       └── middleware.py       # 中间件（监控/槽位追问/二次确认/转人工注入）
├── api/                        # FastAPI 层（为 React/Vue 前端提供开放接口）
│   ├── main.py                 # FastAPI 入口 + CORS + 健康检查
│   ├── schemas.py              # Pydantic 请求/响应模型
│   └── routers/
│       ├── chat.py             # 对话 API（JSON + SSE 流式）+ 意图识别 + 会话历史/评价
│       ├── business.py         # 商品/订单/物流/优惠券/政策查询
│       └── ops.py              # 工单/统计/badcase/FAQ 管理
├── frontend/                   # React 前端（Vite + React 18 + TS + Ant Design）
│   ├── package.json            # 依赖与脚本（dev/build/preview）
│   ├── vite.config.ts          # Vite 配置（/api 代理到 8000）
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx            # 入口（antd 中文 locale）
│       ├── App.tsx             # 侧栏两端：消费者端 / 运营端
│       ├── api.ts              # API 客户端（fetch + SSE 流式解析）
│       ├── types.ts            # 前后端共享类型
│       └── pages/
│           ├── ConsumerChat.tsx  # 消费者聊天页（SSE 流式/停止生成/Markdown/时间戳/动态快捷问题/差评原因/会话切换）
│           ├── OpsLayout.tsx     # 运营端容器（Tab 切换）
│           ├── TicketDesk.tsx    # 人工坐席台（分页/搜索/筛选/轮询角标/坐席回复）
│           ├── DataBoard.tsx     # 数据看板（时间范围筛选）
│           └── BadcasePage.tsx   # badcase 分析（FAQ 盲区一键入库/加载更多）
├── ecommerce/                  # 电商模块
│   ├── __init__.py
│   ├── db.py                   # SQLite 数据层（7 张表 + 种子）
│   ├── chat_service.py         # 统一对话服务（FastAPI 调用）
│   ├── tools.py                # 电商工具组（9 个工具）
│   ├── slots.py                # 槽位管理（缺参追问 / 二次确认）
│   ├── human_handoff.py        # 转人工 + 工单服务
│   ├── intent.py               # 意图分类器（规则 + LLM 混合）
│   ├── faq.py                  # FAQ 直答服务
│   ├── router.py               # 路由分发（转人工 / FAQ 直答 / Agent）
│   ├── memory.py               # 多轮记忆（上下文窗口）
│   ├── chatlog.py              # 对话日志 + 满意度评价 + 统计
│   ├── badcase.py              # badcase 分析（转人工/FAQ盲区/异常回复）
│   └── datasource.py           # 数据源适配器抽象（SQLite/API）
├── rag/                        # RAG 层
│   ├── rag_service.py          # 检索+阈值过滤+引用出处+总结
│   └── vector_stores.py        # 向量库（分域多 collection）
├── model/                      # 模型层
│   └── factory.py              # 模型工厂（惰性单例，.env 加载）
├── utils/                      # 工具层
│   ├── config_handler.py       # YAML 配置加载
│   ├── dashscope_embeddings.py # DashScope Embeddings 封装
│   ├── file_handler.py         # 文件读取 / MD5
│   ├── logger_handler.py       # 日志（带降级）
│   ├── path_tool.py            # 统一路径工具
│   └── prompt_loader.py        # 提示词文件加载
├── config/                     # 配置目录
│   ├── rag.yml / chroma.yml / prompts.yml / ecommerce.yml
├── prompts/                    # 提示词目录（main / presale / intransit / aftersale / rag_summarize）
├── tests/                      # pytest 测试集（tests/test_ecommerce_core.py）
├── data/                       # 数据目录
│   ├── chroma_db/              # Chroma 向量库（知识）
│   ├── ecommerce.db            # 电商业务 SQLite（运行时生成）
│   ├── chat_log.jsonl          # 结构化对话日志（运行时生成）
│   ├── faq_seed.json           # FAQ 种子配置（可编辑，D3）
│   └── kb/manual/              # 知识源（分域：故障/100问/保养/选购）
└── logs/                       # 运行日志（自动生成）
```

---

## 3. 模块与文件详解

### 3.1 根目录

| 文件 | 职责 | 备注 |
|------|------|------|
| `requirements.txt` | 锁定依赖（langchain v1 / chromadb / fastapi / python-dotenv / pytest 等） | 安装：`pip install -r requirements.txt` |
| `test_ecommerce.py` | 冒烟测试脚本（无 API key） | 运行：`python test_ecommerce.py` |
| `DEPLOY.md` | 部署指南：本地运行 / Docker / nginx 反代 / 网页嵌入 / 常见问题 | C3 新增 |
| `Dockerfile` + `docker-compose.yml` + `.dockerignore` | 容器化部署 | C3 新增 |
| `.env.example` | 环境变量模板（DASHSCOPE_API_KEY） | C1 新增，复制为 `.env` 使用 |
| `embed.html` | 网页挂件示例（iframe 嵌入客服页） | D1 新增 |
| `md5.text` | 知识库文件 MD5 去重标记（分域后按域生成 `md5_<域>.text`） | 与 `data/kb/` 知识文件对应 |

### 3.2 `agent/` — Agent 层

| 文件 | 职责 | 备注 |
|------|------|------|
| `react_agent.py` | 用 LangChain v1 `create_agent` 组装电商工具组 + 中间件；`execute_stream()` 流式输出，注入 session_id/user_id/槽位/意图上下文，**多轮历史经滑动窗口接入 Agent**，执行后记录 `last_ctx`/`last_tool_calls` | 核心入口类 `ReactAgent` |
| `tools/middleware.py` | 两个中间件：`monitor_tool`（日志 + 槽位累积 + 缺参追问 + user_id 注入 + 写操作二次确认 + 转人工上下文注入）、`log_before_model`（模型调用日志 + 投诉词告警） | 电商交互机制的核心枢纽 |

### 3.3 `ecommerce/` — 电商模块

| 文件 | 职责 | 备注 |
|------|------|------|
| `__init__.py` | 模块标记 | 空文件 |
| `db.py` | SQLite 数据层：7 张表 + 种子数据；单例惰性初始化，各表独立判断是否灌种子；**线程安全**（RLock 串行化 + 连接异常自愈）；FAQ 种子**优先读外部配置 `data/faq_seed.json`**；商品查询**忽略空格模糊匹配**（第二波） | 数据库文件 `data/ecommerce.db` 自动生成 |
| `tools.py` | 电商工具组 9 个：商品/订单/物流/优惠券/政策/售后/改地址/转人工/知识库检索（RAG 按域惰性缓存） | 缺参/确认逻辑在中间件层，工具只做业务 |
| `slots.py` | 槽位管理：`TOOL_SLOTS`/`SLOT_ASK`/`SlotManager`（跨轮累积、格式校验、二次确认文案） | "缺什么问什么"机制 |
| `human_handoff.py` | 转人工服务：`handoff()` 建工单（携带会话上下文）、`list_open_tickets()`/`resolve_ticket()` | 配合中间件注入上下文 |
| `intent.py` | **意图分类器（A1 升级）**：`RuleIntentClassifier`（关键词+正则）+ `LLMIntentClassifier`（qwen3-max JSON 分类）+ `HybridIntentClassifier`（**规则高置信直接返回，低置信走 LLM，LLM 失败回退规则**）；`get_classifier()` 按配置选择 | 配置 `classifier_type: rule|llm|hybrid`（默认 hybrid） |
| `faq.py` | **FAQ 直答服务**：`FaqService.lookup()` 精确/关键词匹配 FAQ 表，命中直接返回答案（不走 LLM） | 数据在 `faq` 表 / `data/faq_seed.json` |
| `router.py` | **路由分发**：`Router.route()` 输出 `RouteResult(action=escalate|faq|agent, ...)`；FAQ 直答有意图条件防误命中 | 对话服务的入口决策层 |
| `memory.py` | **多轮记忆**：`build_context_messages()` 会话历史滑动窗口接入 Agent 上下文；`summarize_old()` 预留 LLM 摘要 | 窗口大小配置 `memory.max_messages` |
| `chatlog.py` | **对话日志 + 满意度评价 + 统计**：`log_chat()` 返回 `chat_id`，`update_rating()` 写 👍/👎 评价**并支持差评原因 `rating_reason`**（第二波），`stats()` 汇总 | 数据看板/badcase 的数据源 |
| `badcase.py` | **badcase 分析（A3）**：转人工诉求 / FAQ 盲区 / 空或过短回复三类异常案例 | 运营端"badcase 分析"视图的数据源 |
| `datasource.py` | **数据源适配器抽象（D2）**：`DataSource` 接口 + `SqliteDataSource`（当前）+ `ApiDataSource`（真实业务 API 骨架） | 接真实 API 时实现并替换 |
| `chat_service.py` | **统一对话服务**：`ChatService.handle()`（非流式）/`stream()`（流式事件），封装会话恢复→路由→日志→持久化；agent 惰性创建（FAQ/转人工路径无需模型） | FastAPI `routers/chat.py` 调用 |

### 3.4 `rag/` — RAG 层

| 文件 | 职责 | 备注 |
|------|------|------|
| `rag_service.py` | `RagSummarizeService`：按域（默认 manual）检索带相关性分数 → **阈值过滤（A2）** → 拼接上下文（含来源）→ qwen3-max 总结，**回答末尾附参考来源**；无相关资料时明确提示转人工 | 阈值 `chroma.yml` 的 `score_threshold` |
| `vector_stores.py` | `VectorStoreService`：**分域多 collection**，每域独立 collection/目录/k 值/MD5；`similarity_search_with_scores()` 带分数检索（A2）、`load_document()` 灌库、`get_retriever()` 检索 | 域配置见 `config/chroma.yml` 的 `domains` 段 |

### 3.5 `model/` — 模型层

| 文件 | 职责 | 备注 |
|------|------|------|
| `factory.py` | 模型工厂：`get_chat_model()`（qwen3-max，OpenAI 兼容端点）/ `get_embedding_model()`（text-embedding-v4）；**惰性单例**；**自动加载项目根 `.env`（C1）**，缺 key 时抛中文提示 | 已修复：不再 import 即崩 |

### 3.6 `utils/` — 工具层

| 文件 | 职责 | 备注 |
|------|------|------|
| `config_handler.py` | 加载 4 个 YAML 配置（rag / chroma / prompts / ecommerce），模块级导出 `*_config` | 新增配置需同步加加载函数 |
| `dashscope_embeddings.py` | 自定义 DashScope Embeddings（OpenAI 兼容 HTTP，绕开 pydantic v1 兼容问题） | |
| `file_handler.py` | 文件读取（pdf/txt）、MD5 计算、目录文件过滤 | |
| `logger_handler.py` | 双 handler 日志（控制台 INFO + 文件 DEBUG）；文件名含进程号；文件创建失败自动降级为仅控制台 | 已修复 PermissionError 崩溃 |
| `path_tool.py` | `get_abs_path()` 统一相对→绝对路径 | |
| `prompt_loader.py` | 读取 5 个提示词文件（main / presale / intransit / aftersale / rag） | |

### 3.7 `config/` — 配置目录

| 文件 | 内容 | 备注 |
|------|------|------|
| `rag.yml` | `chat_model_name`（qwen3-max）、`embedding_model_name`（text-embedding-v4） | |
| `chroma.yml` | collection 名、数据路径、chunk 大小、检索 k 值、**相关性阈值 score_threshold（A2）**、允许文件类型、知识域 domains 配置 | |
| `prompts.yml` | 5 个提示词文件路径 | |
| `ecommerce.yml` | 电商配置：数据库路径、退换政策、转人工触发词、二次确认工具清单、意图规则 + **分类器类型（默认 hybrid）**、FAQ 直答开关 | |

### 3.8 `prompts/` — 提示词目录

| 文件 | 职责 | 备注 |
|------|------|------|
| `main_prompt.txt` | 通用 Agent 系统提示词（电商人设：售前/售中/售后 + 缺参追问/二次确认/转人工规则 + 安全红线） | 已重写为电商客服版 |
| `presale_prompt.txt` | 售前 Agent 提示词（商品推荐/优惠券/知识库选购） | #1 多 Agent |
| `intransit_prompt.txt` | 售中 Agent 提示词（订单/物流/改地址） | #1 多 Agent |
| `aftersale_prompt.txt` | 售后 Agent 提示词（退换政策/售后申请） | #1 多 Agent |
| `rag_summarize.txt` | RAG 总结提示词（严格基于参考资料） | |

### 3.9 `data/` — 数据目录

| 路径 | 内容 | 备注 |
|------|------|------|
| `data/chroma_db/` | Chroma 向量库（SQLite，含默认 collection 与分域 collection） | 知识检索用，`rag/vector_stores.py` 维护 |
| `data/ecommerce.db` | 电商业务库（自动生成，含种子数据 + FAQ 40 条） | `ecommerce/db.py` 维护 |
| `data/chat_log.jsonl` | 结构化对话日志（自动生成，含满意度评价） | `ecommerce/chatlog.py` 维护，数据看板/badcase 数据源 |
| `data/faq_seed.json` | **FAQ 种子配置（D3）**：可编辑，db.py 优先读取 | 修改后需清空 faq 表或删除库重灌 |
| `data/kb/manual/` | **知识源分域目录**：故障排除 / 扫地机器人100问 / 扫拖一体100问 / 维护保养 / 选购指南 | 灌库：`python -m rag.vector_stores manual`（需 API key） |

### 3.10 `logs/` — 日志目录

| 说明 | 备注 |
|------|------|
| `agent_YYYY-MM-DD_HH-MM-SS_PID.log` | 运行日志（自动生成），文件名含进程号避免冲突 | 可安全清理 |

---

## 4. 核心调用链（速览）

```
用户输入
  → React 前端（frontend/ConsumerChat）→ POST /api/chat 或 /api/chat/stream（SSE）
  → FastAPI（api/routers/chat.py）→ ChatService（ecommerce/chat_service.py）
  → Router.route()（ecommerce/router.py）
      ├─ 命中投诉/负面词  → escalate：建工单直接转人工（不走 LLM）
      ├─ 命中 FAQ（受意图条件约束）→ faq：FAQ 表直答（不走 LLM）
      └─ 其他 → agent：ReactAgent.execute_stream(query, history, intent, ...)
          → create_agent（model = qwen3-max）
          → 中间件 monitor_tool：缺参追问 / 二次确认 / user_id 注入 / 转人工注入
          → 工具组（业务查询 / 写操作 / 转人工 / 分域 RAG 检索）
  → chatlog.log_chat 记日志 → db.save_session 持久化 → 响应返回前端
```

---

## 5. 运行方式

```powershell
cd D:\MyPyCharm\Agent开发
pip install -r requirements.txt
copy .env.example .env        # 编辑 .env 填入 DASHSCOPE_API_KEY
```

后端 API 服务：
```powershell
uvicorn api.main:app --reload --port 8000
# 接口文档：http://localhost:8000/docs（Swagger UI）
# 若 frontend/dist 已构建，http://localhost:8000 直接访问页面（单服务）
```

React 前端（开发模式）：
```powershell
cd frontend
npm install          # 首次
npm run dev          # 开发模式：http://localhost:5173（/api 自动代理到 8000）
npm run build        # 生产构建：输出 dist/，由 FastAPI 托管
```

测试（无需 key）：冒烟 `python test_ecommerce.py`；pytest `pytest tests/ -v`

知识库灌库（需 API key，按域执行）：`python -m rag.vector_stores manual`

完整部署说明见 `DEPLOY.md`（Docker / nginx / 网页嵌入）。
