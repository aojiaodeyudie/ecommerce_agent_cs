# 部署指南（DEPLOY.md）

电商智能客服的部署说明，覆盖本地运行与 Docker 部署。

---

## 1. 环境要求

- Python 3.10+（开发环境为 3.12）
- 阿里云百炼 API Key（`DASHSCOPE_API_KEY`）：qwen3-max 对话 + text-embedding-v4 向量

---

## 2. 本地运行

```powershell
cd D:\MyPyCharm\Agent开发

# 1) 安装依赖
pip install -r requirements.txt

# 2) 配置 API Key（推荐 .env 方式）
copy .env.example .env        # 然后编辑 .env 填入你的 key
# 或临时设置环境变量：
#   $env:DASHSCOPE_API_KEY = "你的key"

# 3) 灌入知识库（首次必做，会调用向量模型，消耗少量额度）
python -m rag.vector_stores manual

# 4) 启动后端（FastAPI）
uvicorn api.main:app --reload --port 8000

# 5) 启动 React 前端（开发模式）
cd frontend
npm install          # 首次
npm run dev          # http://localhost:5173（/api 自动代理到 8000）
```

浏览器打开 `http://localhost:5173`，侧栏切换「消费者端 / 运营端」。

> 生产模式：先 `cd frontend && npm run build`，再启动 uvicorn，
> `http://localhost:8000` 直接提供页面 + API（单服务，见第 6 节）。

---

## 3. 测试

```powershell
# 冒烟测试（无需 API key）
python test_ecommerce.py

# pytest 测试集（无需 API key）
pytest tests/ -v
```

---

## 4. Docker 部署

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f
```

- 服务监听 `0.0.0.0:8000`，访问 `http://服务器IP:8000`（API + 前端页面）
- API Key 通过 `docker compose` 时的环境变量传入（见 `docker-compose.yml`）
- `data/` 目录挂载为卷，数据库/日志/知识库持久化在宿主机

首次启动后需在容器内灌库：
```bash
docker compose exec customer-service python -m rag.vector_stores manual
```

---

## 5. 嵌入网页（网页挂件）

React 前端可直接 iframe 嵌入任意网页（参考 `embed.html`）：

```html
<iframe src="http://你的域名:8000" width="400" height="600"
        style="border:0; border-radius:12px;" allowfullscreen></iframe>
```

- 开发模式指向 `http://localhost:5173`，生产指向你的域名（FastAPI 托管）
- 生产环境建议用 nginx 反代到域名（见下）

---

## 6. nginx 反向代理（生产建议）

```nginx
server {
    listen 80;
    server_name chat.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;      # SSE 长连接，读取超时放宽
    }
}
```

> 前端与 API 由 FastAPI 单服务托管（`frontend/dist`），nginx 仅做反向代理；
> SSE 流式走普通 HTTP 长连接，无需 WebSocket 配置。

---

## 7. 数据与持久化说明

| 路径 | 内容 | 是否需备份 |
|------|------|-----------|
| `data/ecommerce.db` | 业务库（订单/会话/工单/FAQ） | ✅ 建议定期备份 |
| `data/chat_log.jsonl` | 对话日志（看板/badcase 数据源） | ✅ 建议保留 |
| `data/chroma_db/` | 知识向量库 | ✅ 重灌需耗 token |
| `data/kb/` | 知识源文档（可编辑，改后重灌） | ✅ |
| `.env` | API Key | 🔒 勿提交到代码库 |

---

## 8. 常见问题

| 问题 | 处理 |
|------|------|
| `attempt to write a readonly database` | 关闭占用该库的 IDE/数据库工具；杀毒软件加白名单 |
| 知识库检索无结果 | 确认已执行灌库；检查 `config/chroma.yml` 的 `score_threshold`（过高会滤掉所有结果，可调低） |
| 端口被占用 | `uvicorn api.main:app --port 8001`；前端 `cd frontend && npm run dev -- --port 5174` |
| 修改代码后行为不变 | 删除 `__pycache__` 后重启 |
