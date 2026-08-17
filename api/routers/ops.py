# -*- coding: utf-8 -*-
"""
运营管理 API：工单（分页/搜索/回复）/ 统计 / badcase / FAQ 管理
封装 ecommerce/db、chatlog、badcase、human_handoff。
"""
import json

from fastapi import APIRouter, HTTPException, Query

from api.schemas import BadRatingOut, BadcaseOut, FaqIn, FaqOut, StatsOut, TicketOut
from ecommerce import badcase, chatlog
from ecommerce.db import get_db
from ecommerce.human_handoff import resolve_ticket

router = APIRouter(prefix="/api", tags=["ops"])

db = get_db()


# ---------------------------------------------------------------- 工单

def _to_ticket_out(t) -> dict:
    try:
        transcript = json.loads(t["transcript_json"]) if t["transcript_json"] else []
    except json.JSONDecodeError:
        transcript = []
    return TicketOut(
        ticket_id=t["ticket_id"], session_id=t["session_id"],
        user_id=t["user_id"], reason=t["reason"], status=t["status"],
        transcript=transcript, created_at=t["created_at"],
    )


@router.get("/tickets", summary="工单列表（分页/搜索/筛选，第三波）")
def tickets(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, description="搜索：工单号/用户ID/原因"),
    status: str | None = Query(None, description="筛选：open(待处理) / resolved / processing / all"),
):
    rows, total = db.list_tickets(
        status=status, keyword=keyword, limit=size, offset=(page - 1) * size,
    )
    return {
        "items": [_to_ticket_out(t) for t in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/tickets/{ticket_id}/resolve", summary="标记工单已解决")
def resolve(ticket_id: str):
    resolve_ticket(ticket_id)
    return {"ok": True, "ticket_id": ticket_id}


@router.delete("/tickets/{ticket_id}", summary="删除单条工单（软删除）")
def ticket_delete(ticket_id: str):
    """软删除：工单从列表消失，数据保留（deleted=1）。"""
    ok = db.soft_delete_ticket(ticket_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在或已删除")
    return {"ok": True, "ticket_id": ticket_id, "deleted": True}


@router.delete("/tickets", summary="一键删除全部待处理工单（软删除）")
def tickets_delete_all():
    """软删除所有待处理（status != resolved）工单。"""
    count = db.soft_delete_all_open()
    return {"ok": True, "deleted_count": count}


@router.post("/tickets/{ticket_id}/reply", summary="坐席回复工单（追加到会话，第三波）")
def ticket_reply(ticket_id: str, reply: str = Query(..., min_length=1, max_length=2000)):
    """坐席回复：作为客服消息追加到该工单关联的会话（用户下次访问可见）。
    说明：不做实时推送（需 WebSocket，超出当前范围）。"""
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")
    sid = ticket["session_id"]
    if sid:
        row = db.get_session(sid)
        history = []
        if row and row["messages_json"]:
            try:
                history = json.loads(row["messages_json"])
            except json.JSONDecodeError:
                history = []
        history.append({"role": "assistant", "content": f"【人工坐席回复】{reply.strip()}"})
        db.save_session(sid, ticket["user_id"], history, {})
    db.update_ticket_status(ticket_id, "processing")
    return {"ok": True, "ticket_id": ticket_id, "replied": True}


# ---------------------------------------------------------------- 统计 / badcase

@router.get("/stats", response_model=StatsOut, summary="对话统计（支持时间范围，第三波）")
def stats(from_date: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
          to_date: str | None = Query(None, description="结束日期 YYYY-MM-DD")):
    s = chatlog.stats(from_date=from_date, to_date=to_date)
    return StatsOut(
        total=s["total"], intent_dist=s["intent_dist"],
        action_dist=s["action_dist"], escalate_rate=s["escalate_rate"],
        faq_hit_rate=s["faq_hit_rate"], tool_calls=s["tool_calls"],
        # #E4：星级评价统计
        rated_count=s.get("rated_count", 0), bad_count=s.get("bad_count", 0),
        bad_rate=s.get("bad_rate", 0.0), star_dist=s.get("star_dist", {}),
        solved_dist=s.get("solved_dist", {}),
    )


@router.get("/ratings/bad", response_model=list[BadRatingOut], summary="1-3 星差评列表（#E4）")
def bad_ratings(limit: int = Query(50, ge=1, le=500, description="返回条数")):
    """客户评价 1-3 星的记录（含星级/是否解决/问题描述），供人工坐席台跟进。"""
    rows = chatlog.find_low_ratings(limit=limit)
    return [BadRatingOut(
        chat_id=r.get("chat_id", ""), ts=r.get("ts", ""),
        session_id=r.get("session_id"), user_id=r.get("user_id"),
        query=r.get("query", ""), intent=r.get("intent", ""),
        rating=r["rating"], solved=r.get("solved"),
        reason=r.get("rating_reason"), reply=r.get("reply"),
        rating_reply=r.get("rating_reply"), rating_replied_at=r.get("rating_replied_at"),
    ) for r in rows]


@router.delete("/ratings/bad/{chat_id}", summary="删除单条差评（#E5）")
def bad_rating_delete(chat_id: str):
    """从对话日志中删除该条差评记录（数据不可恢复）。"""
    ok = chatlog.delete_rating(chat_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"差评记录 {chat_id} 不存在")
    return {"ok": True, "chat_id": chat_id, "deleted": True}


@router.delete("/ratings/bad", summary="一键删除全部差评（#E5）")
def bad_ratings_delete_all():
    """删除所有 1-3 星差评记录，返回删除条数。"""
    count = chatlog.delete_all_low_ratings()
    return {"ok": True, "deleted_count": count}


@router.post("/ratings/bad/{chat_id}/reply", summary="回复差评（#E5）")
def bad_rating_reply(chat_id: str, reply: str = Query(..., min_length=1, max_length=2000)):
    """坐席回复差评：写入差评记录并追加到该用户会话（消费者端可见）。"""
    ok = chatlog.reply_rating(chat_id, reply)
    if not ok:
        raise HTTPException(status_code=404, detail=f"差评记录 {chat_id} 不存在")
    return {"ok": True, "chat_id": chat_id, "replied": True}


@router.get("/badcase", response_model=BadcaseOut, summary="badcase 分析")
def get_badcase(limit: int = Query(50, ge=1, le=500, description="每类返回条数")):
    s = badcase.summarize(limit=limit)
    return BadcaseOut(escalations=s["escalations"], faq_misses=s["faq_misses"],
                      empty_replies=s["empty_replies"])


# ---------------------------------------------------------------- FAQ 管理

@router.get("/faq", response_model=list[FaqOut], summary="FAQ 列表")
def faq_list(category: str | None = None):
    rows = db.list_faq(category=category, limit=500)
    return [FaqOut(id=r["id"], question=r["question"], answer=r["answer"],
                   keywords=r["keywords"] or "", category=r["category"]) for r in rows]


@router.post("/faq", response_model=FaqOut, summary="新增 FAQ", status_code=201)
def faq_create(item: FaqIn):
    faq_id = db.add_faq(item.question, item.answer, item.keywords, item.category)
    return FaqOut(id=faq_id, question=item.question, answer=item.answer,
                  keywords=item.keywords, category=item.category)


@router.delete("/faq/{faq_id}", summary="删除 FAQ")
def faq_delete(faq_id: int):
    ok = db.delete_faq(faq_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"FAQ {faq_id} 不存在")
    return {"ok": True, "deleted": faq_id}
