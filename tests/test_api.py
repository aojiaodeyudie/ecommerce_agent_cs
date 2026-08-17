# -*- coding: utf-8 -*-
"""
FastAPI 接口测试（无需 DASHSCOPE_API_KEY）
运行：pytest tests/test_api.py -v
覆盖：健康检查 / 业务查询 / 意图 / FAQ 管理 / 对话（FAQ与转人工路径）/ 运营统计
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------- system

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------- business

def test_products_query():
    r = client.get("/api/products", params={"name": "X30"})
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["name"].startswith("X30")


def test_products_all():
    r = client.get("/api/products")
    assert r.status_code == 200
    assert len(r.json()) >= 8


def test_order_found():
    r = client.get("/api/orders/202608160001")
    assert r.status_code == 200
    assert r.json()["status"] == "shipped"


def test_order_not_found():
    r = client.get("/api/orders/999999999999")
    assert r.status_code == 404


def test_logistics():
    r = client.get("/api/logistics/SF1234567890")
    assert r.status_code == 200
    assert r.json()["carrier"] == "顺丰速运"


def test_coupons():
    r = client.get("/api/coupons/1002")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_refund_policy():
    r = client.get("/api/refund-policy", params={"category": "扫地机器人"})
    assert r.status_code == 200
    assert "无理由" in r.json()["policy"]


# ---------------------------------------------------------------- intent

def test_intent_product():
    r = client.post("/api/intent", json={"text": "X30多少钱"})
    assert r.status_code == 200
    assert r.json()["intent"] == "product"


def test_intent_escalate():
    r = client.post("/api/intent", json={"text": "我要投诉"})
    assert r.status_code == 200
    assert r.json()["intent"] == "escalate"


# ---------------------------------------------------------------- chat（无 key 路径）

def test_chat_faq_direct():
    """FAQ 直答路径：不触发 LLM，无需 API key。"""
    r = client.post("/api/chat", json={"message": "运费怎么算", "user_id": "1001"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "faq"
    assert body["reply"] != ""
    assert body["session_id"] != ""


def test_chat_escalate():
    """投诉转人工路径：不触发 LLM，无需 API key。"""
    r = client.post("/api/chat", json={"message": "我要投诉你们客服", "user_id": "1001"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "escalate"
    assert body["ticket_id"] is not None


def test_chat_session_continuity():
    """同 session_id 第二次对话应复用会话。"""
    r1 = client.post("/api/chat", json={"message": "运费怎么算", "user_id": "1001"})
    sid = r1.json()["session_id"]
    r2 = client.post("/api/chat", json={"message": "能开发票吗", "session_id": sid})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid


# ---------------------------------------------------------------- FAQ 管理

def test_faq_crud():
    # 新增
    r = client.post("/api/faq", json={
        "question": "测试问题？", "answer": "测试答案。", "keywords": "测试", "category": "general"})
    assert r.status_code == 201
    faq_id = r.json()["id"]
    # 列表包含
    r = client.get("/api/faq")
    ids = [f["id"] for f in r.json()]
    assert faq_id in ids
    # 删除
    r = client.delete(f"/api/faq/{faq_id}")
    assert r.status_code == 200
    # 再删 404
    r = client.delete(f"/api/faq/{faq_id}")
    assert r.status_code == 404


# ---------------------------------------------------------------- ops

def test_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["total"] >= 0


def test_stats_with_range():
    r = client.get("/api/stats", params={"from": "2026-08-01", "to": "2026-08-31"})
    assert r.status_code == 200
    assert r.json()["total"] >= 0


def test_badcase():
    r = client.get("/api/badcase")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"escalations", "faq_misses", "empty_replies"}


def test_tickets_paged():
    """第三波：工单接口返回分页结构 items/total，支持搜索与状态筛选。"""
    r = client.get("/api/tickets")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "items" in body and "total" in body
    # 分页参数
    r2 = client.get("/api/tickets", params={"page": 1, "size": 5, "status": "all"})
    assert r2.status_code == 200
    assert len(r2.json()["items"]) <= 5
    # 关键词搜索
    r3 = client.get("/api/tickets", params={"keyword": "投诉", "status": "all"})
    assert r3.status_code == 200
    for item in r3.json()["items"]:
        assert "投诉" in item["reason"] or "投诉" in item["ticket_id"]


def test_ticket_soft_delete():
    """软删除：单条删除后列表消失，数据保留；一键删除全部待处理。"""
    # 建一条工单
    r = client.post("/api/chat", json={"message": "我要投诉你们客服", "user_id": "1007"})
    assert r.status_code == 200
    tid = r.json()["ticket_id"]
    assert tid is not None
    # 单条软删除
    r = client.delete(f"/api/tickets/{tid}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    # 列表中不再出现
    r = client.get("/api/tickets", params={"keyword": tid, "status": "all"})
    assert tid not in [i["ticket_id"] for i in r.json()["items"]]
    # 再删返回 404（已删除）
    r = client.delete(f"/api/tickets/{tid}")
    assert r.status_code == 404
    # 一键删除全部待处理
    r = client.delete("/api/tickets")
    assert r.status_code == 200
    assert r.json()["deleted_count"] >= 0
