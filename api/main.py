# -*- coding: utf-8 -*-
"""
电商智能客服 API 入口（FastAPI）
================================
启动：uvicorn api.main:app --reload --port 8000
文档：http://localhost:8000/docs（Swagger UI 自动生成）

路由：
  POST /api/chat            对话（JSON）
  POST /api/chat/stream     对话（SSE 流式，前端逐字输出）
  POST /api/intent          意图识别
  GET  /api/products        商品查询
  GET  /api/orders/{id}     订单查询
  GET  /api/logistics/{no}  物流查询
  GET  /api/coupons/{uid}   优惠券查询
  GET  /api/refund-policy   退换政策
  GET  /api/tickets         待处理工单
  POST /api/tickets/{id}/resolve  标记已解决
  GET  /api/stats           对话统计
  GET  /api/badcase         badcase 分析
  GET/POST/DELETE /api/faq  FAQ 管理
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from api.routers import business, chat, ops

app = FastAPI(
    title="电商智能客服 API",
    description="基于 LangChain ReAct Agent + RAG + 意图路由的智能客服开放接口",
    version="1.0.0",
)

# CORS：#G4 默认仅允许本地开发来源（前端 5173 / 单服务 8000）；
# 生产环境通过环境变量 CORS_ORIGINS 指定（逗号分隔），不再无条件全开
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_origins or _default_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(business.router)
app.include_router(ops.router)


@app.get("/health", tags=["system"], summary="健康检查")
def health():
    return {"status": "ok", "service": "ecommerce-cs-api"}


# 生产模式：若前端已构建（frontend/dist），由 FastAPI 统一托管静态页面，
# 一个服务同时提供 API 与页面（Docker 单容器部署）。
import os
from fastapi.staticfiles import StaticFiles

# 消费者端上传的图片（data/uploads/），优先挂载（避免被 frontend 兜底路由吞掉）
_UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "uploads",
)
os.makedirs(_UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")

_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "dist",
)
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
