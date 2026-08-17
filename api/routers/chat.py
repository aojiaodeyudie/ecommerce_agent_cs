# -*- coding: utf-8 -*-
"""
对话 API：/api/chat（JSON）、/api/chat/stream（SSE 流式）、/api/intent、
图片上传 /api/chat/upload
"""
import json
import os
import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sse_starlette.sse import EventSourceResponse

from api.schemas import ChatRequest, ChatResponse, IntentRequest, IntentResponse
from ecommerce.chat_service import ChatService
from ecommerce.intent import get_classifier
from utils.path_tool import get_abs_path

router = APIRouter(prefix="/api", tags=["chat"])

# 允许的图片格式与大小上限（5MB）
_ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/chat/upload", summary="上传图片（返回可访问 URL）")
async def chat_upload(file: UploadFile = File(..., description="图片文件")):
    """消费者端发送图片：保存到 data/uploads/，返回 /uploads/<文件名> 供消息展示。"""
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的图片格式：{ext or '未知'}（支持 png/jpg/jpeg/gif/webp/bmp）")
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")

    upload_dir = get_abs_path("data/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(upload_dir, fname), "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{fname}", "filename": fname, "size": len(data)}


@router.post("/chat", response_model=ChatResponse, summary="对话（非流式）")
def chat(req: ChatRequest):
    """一次对话回合，返回完整回复。"""
    try:
        service = ChatService()   # 每请求新建 agent，避免线程共享
        result = service.handle(req.message, session_id=req.session_id,
                                user_id=req.user_id, shop_id=req.shop_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话处理失败：{e}")
    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        intent=result.intent,
        action=result.action,
        chat_id=result.chat_id,
        ticket_id=result.ticket_id,
        tool_calls=result.tool_calls,
        elapsed_ms=result.elapsed_ms,
    )


@router.post("/chat/stream", summary="对话（SSE 流式）")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话。事件：
      intent：{intent, action, session_id}
      token ：文本片段（逐段输出）
      done  ：{reply, intent, action, session_id, chat_id, tool_calls}
      error ：{message}
    前端用 EventSource/fetch 读取。
    """
    def gen():
        service = ChatService()
        try:
            for event in service.stream(req.message, session_id=req.session_id,
                                        user_id=req.user_id, shop_id=req.shop_id):
                yield event
        except Exception as e:
            yield {"event": "error",
                   "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(gen(), ping=15)


@router.post("/intent", response_model=IntentResponse, summary="意图识别")
def intent(req: IntentRequest):
    """单独暴露意图分类（供前端/其他系统使用）。"""
    result = get_classifier().classify(req.text)
    return IntentResponse(intent=result.intent, confidence=result.confidence,
                          matched=result.matched)


# ---------------------------------------------------------------- 会话辅助

@router.get("/chat/history/{session_id}", summary="获取会话历史")
def chat_history(session_id: str):
    """返回该会话的历史消息列表（前端刷新页面后恢复对话）。"""
    from ecommerce.db import get_db
    row = get_db().get_session(session_id)
    if row is None:
        return {"session_id": session_id, "messages": []}
    try:
        messages = json.loads(row["messages_json"]) if row["messages_json"] else []
    except json.JSONDecodeError:
        messages = []
    return {"session_id": session_id, "messages": messages}


@router.get("/chat/sessions", summary="会话列表（第四波）")
def chat_sessions(user_id: str = Query("1001", description="用户ID"),
                  limit: int = Query(50, ge=1, le=100, description="返回条数")):
    """该用户的历史会话列表（含消息数/最后一条摘要/更新时间），供前端切换会话。"""
    from ecommerce.db import get_db
    rows = get_db().list_sessions(user_id=user_id, limit=limit)
    items = []
    for r in rows:
        try:
            msgs = json.loads(r["messages_json"]) if r["messages_json"] else []
        except json.JSONDecodeError:
            msgs = []
        items.append({
            "session_id": r["session_id"],
            "message_count": len(msgs),
            "last_message": str(msgs[-1].get("content", ""))[:60] if msgs else "",
            "updated_at": r["updated_at"],
        })
    return {"items": items, "total": len(items)}


@router.post("/chat/rating", summary="满意度评价（星级）")
def chat_rating(chat_id: str, rating: int, solved: str | None = None, reason: str | None = None):
    """
    对某次回答评价（#E3）：
      rating=1~5 星（1很不满 / 2不满意 / 3一般 / 4满意 / 5很满意），
      -1 兼容旧版差评；
      solved：是否解决问题（"已解决"/"未解决"），选填；
      reason：问题描述，选填。
    """
    if rating not in (-1, 1, 2, 3, 4, 5):
        raise HTTPException(status_code=400, detail="rating 只能为 1~5（星）或 -1（旧版差评）")
    if solved not in (None, "已解决", "未解决"):
        raise HTTPException(status_code=400, detail="solved 只能为 已解决 / 未解决")
    from ecommerce import chatlog
    ok = chatlog.update_rating(chat_id, rating, reason, solved)
    if not ok:
        raise HTTPException(status_code=404, detail=f"对话记录 {chat_id} 不存在")
    return {"ok": True, "chat_id": chat_id, "rating": rating, "solved": solved, "reason": reason}
