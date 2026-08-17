# -*- coding: utf-8 -*-
"""
结构化对话日志（数据飞轮起点）
==============================
每次对话追加一行 JSON 到 data/chat_log.jsonl：
  时间 / 会话 / 用户 / 输入 / 意图 / 路由动作 / 回复 / 工具调用 / 耗时
供数据看板统计（意图分布、转人工率、FAQ 命中率）与后续 badcase 分析。
"""
import json
import os
import uuid
from datetime import datetime

from utils.path_tool import get_abs_path
from utils.logger_handler import logger

LOG_FILE = get_abs_path("data/chat_log.jsonl")


def log_chat(*, session_id, user_id, query, intent, action, reply=None,
             matched=None, tool_calls=None, elapsed_ms=None,
             faq_hit=False, escalated=False, ticket_id=None, chat_id=None):
    """记录一次完整对话回合，返回 chat_id（供满意度评价定位）。"""
    chat_id = chat_id or uuid.uuid4().hex[:12]
    entry = {
        "chat_id": chat_id,
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": session_id,
        "user_id": user_id,
        "query": query,
        "intent": intent,
        "action": action,              # escalate | faq | agent
        "faq_hit": faq_hit,
        "escalated": escalated,
        "ticket_id": ticket_id,
        "matched": matched or [],
        "tool_calls": tool_calls or [],
        "elapsed_ms": elapsed_ms,
        "reply": (reply or "")[:500],
        "rating": None,                # 满意度：1 满意 / -1 不满意（B3）
    }
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning(f"[chatlog]写入失败：{e}")
    return chat_id


def update_rating(chat_id: str, rating: int, reason: str | None = None,
                  solved: str | None = None) -> bool:
    """
    按 chat_id 更新满意度评价（#E3：星级评分）。
    :param rating: 1~5 星；-1 兼容旧版差评。
    :param reason: 问题描述（选填）
    :param solved: 是否解决问题（"已解决"/"未解决"）
    重写日志文件。
    """
    if not os.path.exists(LOG_FILE):
        return False
    rows = load_logs()
    changed = False
    for r in rows:
        if r.get("chat_id") == chat_id:
            r["rating"] = rating
            if reason:
                r["rating_reason"] = reason
            if solved:
                r["solved"] = solved
            changed = True
    if not changed:
        return False
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        logger.warning(f"[chatlog]评价写入失败：{e}")
        return False


def load_logs(limit: int | None = None) -> list[dict]:
    """读取全部对话日志（可选限制条数）。"""
    if not os.path.exists(LOG_FILE):
        return []
    rows = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None:
        rows = rows[-limit:]
    return rows


def find_low_ratings(limit: int = 50) -> list[dict]:
    """1-3 星差评记录（#E4：运营端坐席台展示，含星级/是否解决/问题描述）。"""
    rows = [
        r for r in load_logs()
        if isinstance(r.get("rating"), int) and 1 <= r["rating"] <= 3
    ]
    return rows[-limit:]


def _rewrite_logs(rows: list[dict]) -> bool:
    """整文件重写日志，返回是否成功。"""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        logger.warning(f"[chatlog]日志重写失败：{e}")
        return False


def delete_rating(chat_id: str) -> bool:
    """删除单条对话日志记录（#E5：运营端删除差评），返回是否删除成功。"""
    rows = load_logs()
    remain = [r for r in rows if r.get("chat_id") != chat_id]
    if len(remain) == len(rows):
        return False
    return _rewrite_logs(remain)


def delete_all_low_ratings() -> int:
    """一键删除全部 1-3 星差评记录（#E5），返回删除条数。"""
    rows = load_logs()
    remain = [
        r for r in rows
        if not (isinstance(r.get("rating"), int) and 1 <= r["rating"] <= 3)
    ]
    deleted = len(rows) - len(remain)
    if deleted > 0:
        _rewrite_logs(remain)
    return deleted


def reply_rating(chat_id: str, reply: str) -> bool:
    """
    坐席回复差评（#E5）：
      - 在日志记录上写入 rating_reply / rating_replied_at（列表可见"已回复"）；
      - 追加到该记录关联的会话（session_id），消费者端下次访问可见。
    """
    reply = (reply or "").strip()
    if not reply:
        return False
    rows = load_logs()
    target = None
    for r in rows:
        if r.get("chat_id") == chat_id:
            r["rating_reply"] = reply
            r["rating_replied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            target = r
            break
    if target is None:
        return False
    if not _rewrite_logs(rows):
        return False
    # 追加到关联会话，让用户在消费者端可见
    sid = target.get("session_id")
    if sid:
        try:
            from ecommerce.db import get_db
            db = get_db()
            row = db.get_session(sid)
            history = []
            if row and row["messages_json"]:
                try:
                    history = json.loads(row["messages_json"])
                except json.JSONDecodeError:
                    history = []
            history.append({
                "role": "assistant",
                "content": f"【人工坐席回复】{reply}",
            })
            db.save_session(sid, target.get("user_id"), history, {})
            logger.info(f"[chatlog]差评回复已写入会话 {sid}")
        except Exception as e:
            logger.warning(f"[chatlog]差评回复写入会话失败：{e}")
    return True


def stats(from_date: str | None = None, to_date: str | None = None) -> dict:
    """
    汇总统计（第三波支持时间范围）：总数 / 意图分布 / 路由动作分布 / 转人工率 / FAQ 命中率。
    #E4 增加星级评价统计：已评价数 / 差评数 / 差评率 / 星级分布 / 解决情况。
    :param from_date: 起始日期（YYYY-MM-DD，含）
    :param to_date:   结束日期（YYYY-MM-DD，含）
    """
    rows = load_logs()
    if from_date:
        rows = [r for r in rows if (r.get("ts") or "")[:10] >= from_date]
    if to_date:
        rows = [r for r in rows if (r.get("ts") or "")[:10] <= to_date]

    total = len(rows)
    if total == 0:
        return {
            "total": 0, "intent_dist": {}, "action_dist": {},
            "escalate_rate": 0.0, "faq_hit_rate": 0.0, "tool_calls": 0,
            "rated_count": 0, "bad_count": 0, "bad_rate": 0.0,
            "star_dist": {}, "solved_dist": {},
        }

    intent_dist: dict[str, int] = {}
    action_dist: dict[str, int] = {}
    escalate = 0
    faq_hit = 0
    tool_calls = 0
    # 星级评价统计（#E4）
    rated_count = 0
    bad_count = 0
    star_dist: dict[int, int] = {}
    solved_dist: dict[str, int] = {}
    for r in rows:
        intent_dist[r.get("intent", "unknown")] = intent_dist.get(r.get("intent", "unknown"), 0) + 1
        action_dist[r.get("action", "unknown")] = action_dist.get(r.get("action", "unknown"), 0) + 1
        if r.get("escalated"):
            escalate += 1
        if r.get("faq_hit"):
            faq_hit += 1
        tool_calls += len(r.get("tool_calls") or [])
        # 星级评价
        rating = r.get("rating")
        if isinstance(rating, int) and 1 <= rating <= 5:
            rated_count += 1
            star_dist[rating] = star_dist.get(rating, 0) + 1
            if rating <= 3:
                bad_count += 1
            solved = r.get("solved")
            if solved:
                solved_dist[solved] = solved_dist.get(solved, 0) + 1

    return {
        "total": total,
        "intent_dist": dict(sorted(intent_dist.items(), key=lambda x: -x[1])),
        "action_dist": dict(sorted(action_dist.items(), key=lambda x: -x[1])),
        "escalate_rate": round(escalate / total, 3),
        "faq_hit_rate": round(faq_hit / total, 3),
        "tool_calls": tool_calls,
        "rated_count": rated_count,
        "bad_count": bad_count,
        "bad_rate": round(bad_count / rated_count, 3) if rated_count else 0.0,
        "star_dist": {str(k): star_dist.get(k, 0) for k in range(1, 6)},
        "solved_dist": dict(sorted(solved_dist.items(), key=lambda x: -x[1])),
    }


if __name__ == "__main__":
    # 自测：写 3 条示例日志再统计
    log_chat(session_id="S1", user_id="1001", query="运费怎么算", intent="faq",
             action="faq", reply="全场满99包邮…", faq_hit=True)
    log_chat(session_id="S1", user_id="1001", query="我的订单发货了吗", intent="order",
             action="agent", tool_calls=["get_order_info"], elapsed_ms=3200)
    log_chat(session_id="S2", user_id="1002", query="我要投诉", intent="escalate",
             action="escalate", escalated=True, ticket_id="TK001")
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
