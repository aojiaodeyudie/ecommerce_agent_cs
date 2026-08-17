# -*- coding: utf-8 -*-
"""
pytest 测试集（C2）
===================
运行：pytest tests/ -v
覆盖：意图分类 / FAQ / 路由 / 数据库 / 槽位 / 记忆窗口 / 日志
说明：不依赖 DASHSCOPE_API_KEY（LLM 路径会自动回退规则）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecommerce.db import get_db
from ecommerce.intent import RuleIntentClassifier
from ecommerce.faq import get_faq_service
from ecommerce.router import get_router
from ecommerce.slots import SlotManager
from ecommerce.memory import build_context_messages
from ecommerce import chatlog


# ---------------------------------------------------------------- 意图分类

@pytest.mark.parametrize("text,expect", [
    ("X30多少钱", "product"),
    ("我的订单发货了吗", "order"),
    ("快递到哪了", "logistics"),
    ("有优惠券吗", "coupon"),
    ("我要退货", "refund"),
    ("能开发票吗", "policy"),
    ("运费怎么算", "faq"),
    ("机器人老是报错怎么办", "knowledge"),
    ("我要投诉你们客服", "escalate"),
    ("今天天气不错", "chitchat"),
    ("我要退货 订单202608120001", "refund"),  # 带订单号的售后 → refund
])
def test_intent_rule_classifier(text: str, expect: str):
    clf = RuleIntentClassifier()
    assert clf.classify(text).intent == expect


# ---------------------------------------------------------------- FAQ

def test_faq_hit():
    svc = get_faq_service()
    assert svc.lookup("运费怎么算？") is not None
    assert svc.lookup("能开发票吗") is not None
    assert svc.lookup("怎么退货啊") is not None


def test_faq_miss():
    svc = get_faq_service()
    assert svc.lookup("随便聊聊天气") is None


# ---------------------------------------------------------------- 路由

def test_route_faq_direct():
    r = get_router().route("有优惠券吗")
    assert r.action == "faq"
    assert r.reply is not None


def test_route_escalate():
    r = get_router().route("我要投诉你们客服")
    assert r.action == "escalate"
    assert r.ticket_id is not None


def test_route_agent_for_refund_with_order_no():
    # 带订单号的售后请求必须走 Agent（防 FAQ 误命中）
    r = get_router().route("我要退货 订单202608120001")
    assert r.action == "agent"


def test_route_agent_for_product():
    r = get_router().route("X30多少钱")
    assert r.action == "agent"
    assert r.intent == "product"


# ---------------------------------------------------------------- 数据库

def test_db_roundtrip():
    db = get_db()
    db.save_session("PYTEST-SID", "1001", [{"role": "user", "content": "hi"}], {"k": "v"})
    row = db.get_session("PYTEST-SID")
    assert row is not None
    assert row["user_id"] == "1001"


def test_db_products_seeded():
    db = get_db()
    assert len(db.list_products()) >= 8
    assert len(db.list_faq()) >= 40


# ---------------------------------------------------------------- 槽位

def test_slots_missing():
    sm = SlotManager()
    assert sm.missing_slots("get_order_info", {}) == ["order_id"]


def test_slots_accumulate():
    sm = SlotManager()
    sm.set("order_id", "202608160001")
    assert sm.missing_slots("get_order_info", {}) == []


def test_slots_invalid():
    sm = SlotManager()
    assert sm.missing_slots("get_order_info", {"order_id": "abc"}) == ["order_id"]


def test_slots_confirm():
    sm = SlotManager()
    assert sm.confirm_tool_call("create_after_sale",
                                {"order_id": "x", "reason": "y"}) is not None
    assert sm.confirm_tool_call("create_after_sale",
                                {"order_id": "x", "reason": "y", "confirm": "yes"}) is None


# ---------------------------------------------------------------- 记忆窗口

def test_memory_window():
    hist = [{"role": "user", "content": f"问题{i}"} for i in range(1, 30)]
    msgs = build_context_messages(hist, max_messages=5)
    assert len(msgs) == 5
    assert msgs[0].content == "问题25"  # 取最近 5 条


# ---------------------------------------------------------------- 多 Agent 路由（#1）

def test_route_agent_mapping():
    from ecommerce.chat_service import ChatService
    svc = ChatService()
    assert svc._route_agent("product") == "presale"
    assert svc._route_agent("knowledge") == "presale"
    assert svc._route_agent("coupon") == "presale"
    assert svc._route_agent("order") == "intransit"
    assert svc._route_agent("logistics") == "intransit"
    assert svc._route_agent("refund") == "aftersale"
    assert svc._route_agent("escalate") == "general"    # 不走 Agent，兜底
    assert svc._route_agent("unknown_xx") == "general"  # 未知意图兜底


def test_agent_specs_have_scoped_tools():
    from agent.react_agent import AGENT_SPECS
    presale_names = {t.name for t in AGENT_SPECS["presale"][0]}
    assert presale_names == {"get_product_info", "search_knowledge_base", "query_coupon"}
    intransit_names = {t.name for t in AGENT_SPECS["intransit"][0]}
    assert intransit_names == {"get_order_info", "get_logistics", "update_address"}
    aftersale_names = {t.name for t in AGENT_SPECS["aftersale"][0]}
    assert aftersale_names == {"get_order_info", "create_after_sale", "check_refund_policy"}
    # 通用 Agent 保留全 9 工具
    assert len(AGENT_SPECS["general"][0]) == 9


# ---------------------------------------------------------------- 对话日志

def test_chatlog_rating():
    cid = chatlog.log_chat(session_id="PYTEST", user_id="1001", query="测试",
                           intent="faq", action="faq", reply="答")
    assert chatlog.update_rating(cid, 1) is True
    rows = chatlog.load_logs()
    target = [r for r in rows if r.get("chat_id") == cid]
    assert target and target[0]["rating"] == 1
    assert chatlog.update_rating("NO-SUCH-ID", 1) is False
