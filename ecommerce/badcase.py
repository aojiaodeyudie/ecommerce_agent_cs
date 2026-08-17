# -*- coding: utf-8 -*-
"""
badcase 分析（A3）
=================
基于 data/chat_log.jsonl 找出客服表现不佳的案例，定位改进方向：
  1. 转人工记录：用户带着什么诉求转人工（投诉/不满高频主题）
  2. FAQ 盲区：意图是常见问题类（faq/policy/coupon/refund）却走了 Agent
     —— 说明 FAQ 库没覆盖，是补知识库的候选
  3. 空/过短回复：Agent 回答了但内容为空或极短（可能生成失败/答非所问）
"""
from ecommerce import chatlog

# 应该被 FAQ 覆盖的意图（未覆盖即盲区）
_FAQ_LIKE_INTENTS = {"faq", "policy", "coupon", "refund"}

EMPTY_REPLY_THRESHOLD = 10  # 回复少于该字数视为异常


def find_escalations(limit: int = 50) -> list[dict]:
    """转人工前的用户提问（投诉/负面诉求）。"""
    rows = [r for r in chatlog.load_logs() if r.get("escalated")]
    return rows[-limit:]


def find_faq_misses(limit: int = 50) -> list[dict]:
    """常见问题类意图却走了 Agent 的记录（FAQ 盲区候选）。"""
    rows = [
        r for r in chatlog.load_logs()
        if r.get("action") == "agent" and r.get("intent") in _FAQ_LIKE_INTENTS
    ]
    return rows[-limit:]


def find_empty_replies(limit: int = 50) -> list[dict]:
    """Agent 回复为空或过短的记录（生成失败/答非所问候选）。"""
    rows = [
        r for r in chatlog.load_logs()
        if r.get("action") == "agent"
        and len((r.get("reply") or "").strip()) < EMPTY_REPLY_THRESHOLD
    ]
    return rows[-limit:]


def summarize(limit: int = 50) -> dict:
    """汇总三类 badcase（第四波：limit 控制每类返回条数）。"""
    return {
        "escalations": find_escalations(limit),
        "faq_misses": find_faq_misses(limit),
        "empty_replies": find_empty_replies(limit),
    }


if __name__ == "__main__":
    import json
    s = summarize()
    for key, rows in s.items():
        print(f"=== {key}: {len(rows)} 条 ===")
        for r in rows:
            print(f"  [{r.get('ts')}] {r.get('query', '')[:40]} | intent={r.get('intent')} | reply={str(r.get('reply'))[:30]}")
