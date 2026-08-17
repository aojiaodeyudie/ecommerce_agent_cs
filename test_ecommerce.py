# -*- coding: utf-8 -*-
"""
电商智能客服无 key 回归测试（阶段一 + 阶段二）
运行：python test_ecommerce.py
覆盖：数据库/工具/槽位/会话/工单 + 意图分类/FAQ直答/路由分发
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("1. 数据库建库与种子数据")
from ecommerce.db import get_db
db = get_db()
print(f"  商品数: {len(db.list_products())}")
print(f"  FAQ 条数: {len(db.list_faq())}")
print(f"  用户1001订单数: {len(db.list_orders_by_user('1001'))}")
print(f"  用户1002可用优惠券: {len(db.list_coupons_by_user('1002'))}")

print("=" * 60)
print("2. 工具函数（不依赖 API key）")
from ecommerce.tools import (
    get_product_info, get_order_info, get_logistics, query_coupon,
    check_refund_policy, create_after_sale, update_address, escalate_to_human,
)
print("  [get_product_info] X30 ->", get_product_info.invoke({"product": "X30"})[:50].replace("\n", " | "), "...")
print("  [get_order_info] 202608160001 ->", get_order_info.invoke({"order_id": "202608160001"})[:50].replace("\n", " | "))
print("  [get_logistics] SF1234567890 ->", get_logistics.invoke({"tracking_no": "SF1234567890"})[:50].replace("\n", " | "))
print("  [query_coupon] 1002 ->", query_coupon.invoke({"user_id": "1002"})[:50])
print("  [check_refund_policy] 扫地机器人 ->", check_refund_policy.invoke({"category": "扫地机器人"})[:40], "...")
print("  [create_after_sale] ->", create_after_sale.invoke({"order_id": "202608120001", "reason": "质量问题", "confirm": "yes"})[:40])
print("  [update_address] 已发货订单 ->", update_address.invoke({"order_id": "202608160001", "new_address": "测试", "confirm": "yes"})[:40])
print("  [escalate_to_human] ->", escalate_to_human.invoke({"reason": "用户要求人工"})[:40])

print("=" * 60)
print("3. 槽位管理")
from ecommerce.slots import SlotManager
sm = SlotManager()
missing = sm.missing_slots("get_order_info", {})
print(f"  get_order_info 缺参: {missing}")
print(f"  追问文案: {sm.ask_message(missing)[:45]}...")
sm.set("order_id", "202608160001")
print(f"  累积后缺参: {sm.missing_slots('get_order_info', {})}")
print(f"  confirm=yes 放行: {sm.confirm_tool_call('create_after_sale', {'order_id': 'x', 'reason': 'y', 'confirm': 'yes'})}")

print("=" * 60)
print("4. 会话持久化")
db.save_session("TEST-SID", "1001", [{"role": "user", "content": "你好"}], {"order_id": "202608160001"})
row = db.get_session("TEST-SID")
print(f"  写入并读回: messages={row['messages_json']}  slots={row['slots_json']}")

print("=" * 60)
print("5. 意图分类")
from ecommerce.intent import get_classifier
clf = get_classifier()
intent_cases = [
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
]
pass_count = 0
for text, expect in intent_cases:
    r = clf.classify(text)
    ok = "✅" if r.intent == expect else "❌"
    if r.intent == expect:
        pass_count += 1
    print(f"  {ok} {text!r:18} -> {r.intent:10} (期望 {expect}) conf={r.confidence:.2f}")
print(f"  意图分类通过率: {pass_count}/{len(intent_cases)}")

print("=" * 60)
print("6. FAQ 直答")
from ecommerce.faq import get_faq_service
faq_svc = get_faq_service()
faq_cases = [
    ("运费怎么算？", True),
    ("能开发票吗", True),
    ("怎么退货啊", True),
    ("随便聊聊天气", False),
]
for text, expect_hit in faq_cases:
    ans = faq_svc.lookup(text)
    ok = "✅" if (ans is not None) == expect_hit else "❌"
    print(f"  {ok} {text!r:14} -> {'命中: ' + ans[:30] if ans else '未命中'}")

print("=" * 60)
print("7. 路由分发")
from ecommerce.router import get_router
router = get_router()
route_cases = [
    ("X30多少钱", "agent"),
    ("我的订单发货了吗", "agent"),
    ("有优惠券吗", "faq"),
    ("我要退货", "faq"),
    ("我要退货 订单202608120001", "agent"),
    ("我要投诉你们客服", "escalate"),
]
pass_count = 0
for text, expect in route_cases:
    r = router.route(text, session_id="TEST-SID", user_id="1001")
    ok = "✅" if r.action == expect else "❌"
    if r.action == expect:
        pass_count += 1
    print(f"  {ok} {text!r:26} -> {r.action:8} intent={r.intent:10} "
          f"{('工单:' + r.ticket_id) if r.ticket_id else ''}")
print(f"  路由通过率: {pass_count}/{len(route_cases)}")

print("=" * 60)
print("8. 多轮记忆（上下文窗口）")
from ecommerce.memory import build_context_messages
hist = [{"role": "user", "content": f"问题{i}"} for i in range(1, 30)]
msgs = build_context_messages(hist, max_messages=5)
print(f"  30 条历史 -> 窗口 5 条: {len(msgs)} 条，首条内容: {msgs[0].content}")

print("=" * 60)
print("9. 对话日志与统计")
from ecommerce import chatlog
chatlog.log_chat(session_id="TEST", user_id="1001", query="运费怎么算", intent="faq",
                 action="faq", reply="全场满99包邮", faq_hit=True)
chatlog.log_chat(session_id="TEST", user_id="1001", query="查订单", intent="order",
                 action="agent", tool_calls=["get_order_info"], elapsed_ms=1200)
s = chatlog.stats()
print(f"  日志总数: {s['total']}（含历史自测数据，>=3 即正常）")
print(f"  意图分布: {s['intent_dist']}")

print("=" * 60)
print("ALL TESTS DONE")
