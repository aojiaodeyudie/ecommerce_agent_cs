# -*- coding: utf-8 -*-
"""
转人工 + 工单服务
================
创建工单并保存完整对话记录，供人工坐席台读取。
中间件（agent/tools/middleware.py）在 escalate_to_human 工具调用前，
把当前会话上下文（session_id / user_id / 对话记录）**显式传入** handoff()，
使工单自动带上用户信息和完整上下文，坐席可无缝接管。

#G3 已移除模块级全局上下文（_handoff_ctx）：
  旧实现用全局 dict 传递上下文，多用户并发时后调用者会覆盖前者，
  导致工单携带错误的会话信息；现改为调用方显式传参，天然线程安全。
"""
from ecommerce.db import get_db
from utils.logger_handler import logger


def handoff(reason: str, session_id=None, user_id=None, transcript=None) -> str:
    """
    创建工单。
    :param reason: 转人工原因
    :param session_id: 会话 ID（中间件从运行时上下文取）
    :param user_id: 用户 ID
    :param transcript: 完整对话记录（list[dict]）
    """
    db = get_db()
    ticket_id = db.create_ticket(session_id, user_id, reason, transcript)
    logger.info(f"[handoff]创建工单 {ticket_id}：用户={user_id} 原因={reason}")
    return ticket_id


def list_open_tickets():
    db = get_db()
    return db.list_open_tickets()


def resolve_ticket(ticket_id: str):
    db = get_db()
    db.resolve_ticket(ticket_id)
