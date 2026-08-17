# -*- coding: utf-8 -*-
"""
转人工 + 工单服务
=================
创建工单并保存完整对话记录，供人工坐席台读取。
中间件（agent/tools/middleware.py）在 escalate_to_human 工具调用前，
把当前会话上下文（session_id / user_id / 对话记录）注入本模块，
使工单自动带上用户信息和完整上下文，坐席可无缝接管。
"""
from ecommerce.db import get_db
from utils.logger_handler import logger

# 当前会话上下文（单用户演示场景足够；多用户并发需改为按 session 隔离）
_handoff_ctx: dict = {}


def set_handoff_context(session_id=None, user_id=None, transcript=None):
    _handoff_ctx["session_id"] = session_id
    _handoff_ctx["user_id"] = user_id
    _handoff_ctx["transcript"] = transcript or []


def clear_handoff_context():
    _handoff_ctx.clear()


def handoff(reason: str, session_id=None, user_id=None, transcript=None) -> str:
    """
    创建工单。
    优先使用调用方显式传入的会话信息，否则回退到中间件注入的上下文。
    """
    db = get_db()
    sid = session_id or _handoff_ctx.get("session_id")
    uid = user_id or _handoff_ctx.get("user_id")
    tr = transcript if transcript is not None else _handoff_ctx.get("transcript")
    ticket_id = db.create_ticket(sid, uid, reason, tr)
    logger.info(f"[handoff]创建工单 {ticket_id}：用户={uid} 原因={reason}")
    return ticket_id


def list_open_tickets():
    db = get_db()
    return db.list_open_tickets()


def resolve_ticket(ticket_id: str):
    db = get_db()
    db.resolve_ticket(ticket_id)
