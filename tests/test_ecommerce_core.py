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


# ---------------------------------------------------------------- #F9 商品按商家拆分

def test_products_shop_scoped():
    db = get_db()
    all_prods = db.list_products()
    assert len(all_prods) >= 40                     # 6 家商家共 50 款
    shop_ids = {p["shop_id"] for p in all_prods}
    assert shop_ids == {"shop_a", "shop_b", "shop_c", "shop_d", "shop_e", "shop_f"}


def test_product_lookup_shop_isolation():
    db = get_db()
    # 星辉数码(S10) 只属于 shop_a
    assert db.get_product_by_name("星辉S10", shop_id="shop_a") is not None
    assert db.get_product_by_name("星辉S10", shop_id="shop_b") is None
    # 智能客服全店可查
    assert db.get_product_by_name("星辉S10") is not None
    # 冗余词匹配（#G1）
    assert db.get_product_by_name("星辉S10手机多少钱", shop_id="shop_a") is not None
    assert db.get_product_by_name("车厘子多少钱", shop_id="shop_e") is not None
    assert db.get_product_by_name("三体多少钱", shop_id="shop_f") is not None


# ---------------------------------------------------------------- #E3/#E5 星级评价与差评

def test_rating_star_and_solved():
    cid = chatlog.log_chat(session_id="PYTEST-STAR", user_id="1001", query="测试",
                           intent="faq", action="faq", reply="答")
    assert chatlog.update_rating(cid, 3, "一般", "未解决") is True
    rows = chatlog.load_logs()
    t = [r for r in rows if r.get("chat_id") == cid][0]
    assert t["rating"] == 3
    assert t["solved"] == "未解决"
    # 覆盖更新
    assert chatlog.update_rating(cid, 5, None, "已解决") is True
    t2 = [r for r in chatlog.load_logs() if r.get("chat_id") == cid][0]
    assert t2["rating"] == 5
    assert t2["solved"] == "已解决"


def test_find_low_ratings():
    cid = chatlog.log_chat(session_id="PYTEST-LOW", user_id="1001", query="测试",
                           intent="faq", action="faq", reply="答")
    chatlog.update_rating(cid, 2, "回答不准确", "未解决")
    lows = chatlog.find_low_ratings()
    assert any(r.get("chat_id") == cid and r["rating"] == 2 for r in lows)
    # 4-5 星不应出现在差评列表
    cid5 = chatlog.log_chat(session_id="PYTEST-HIGH", user_id="1001", query="测试",
                            intent="faq", action="faq", reply="答")
    chatlog.update_rating(cid5, 5, None, "已解决")
    lows2 = chatlog.find_low_ratings()
    assert not any(r.get("chat_id") == cid5 for r in lows2)


def test_stats_includes_ratings():
    s = chatlog.stats()
    assert "rated_count" in s and "bad_count" in s and "bad_rate" in s
    assert "star_dist" in s and "solved_dist" in s


# ---------------------------------------------------------------- #G2 商家身份注入

def test_shop_profile_injection():
    from ecommerce.shop_profiles import build_shop_system_prompt, get_shop_profile
    # 商家注入：店名/经营范围出现在提示词中
    p = build_shop_system_prompt("【BASE】", "shop_a")
    assert "星辉数码旗舰店" in p and "数码" in p
    # 智能客服不注入商家身份
    assert build_shop_system_prompt("【BASE】", None) == "【BASE】"
    assert build_shop_system_prompt("【BASE】", "ai") == "【BASE】"
    # 未知商家回退
    assert get_shop_profile("unknown_shop") is None


# ---------------------------------------------------------------- #G3 转人工显式传参

def test_handoff_explicit_context():
    from ecommerce.human_handoff import handoff
    from ecommerce.db import get_db
    ticket_id = handoff("测试转人工", session_id="S-HANDOFF", user_id="1001",
                        transcript=[{"role": "user", "content": "hi"}])
    row = get_db().get_ticket(ticket_id)
    assert row is not None
    import json
    transcript = json.loads(row["transcript_json"])
    assert transcript and transcript[0]["content"] == "hi"
    assert row["session_id"] == "S-HANDOFF"
