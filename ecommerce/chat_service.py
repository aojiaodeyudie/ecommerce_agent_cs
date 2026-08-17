# -*- coding: utf-8 -*-
"""
统一对话服务（FastAPI 与 Streamlit 共用）
========================================
把 app.py 消费者端的对话处理逻辑抽成可复用服务，供：
  - FastAPI：/api/chat（JSON）与 /api/chat/stream（SSE）
  - Streamlit app.py（后续可迁移复用）

流程：会话恢复 → 路由分发（escalate/faq/agent）→ 日志 → 持久化。
"""
import json
import time
import uuid
from dataclasses import dataclass, field

from ecommerce.db import get_db
from ecommerce.router import get_router
from ecommerce import chatlog


@dataclass
class ChatResult:
    session_id: str
    reply: str
    intent: str
    action: str          # escalate | faq | agent
    chat_id: str
    slots: dict = field(default_factory=dict)
    ticket_id: str | None = None
    elapsed_ms: int = 0
    matched: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)


def _new_session_id() -> str:
    return f"S{uuid.uuid4().hex[:8].upper()}"


def _restore_session(session_id: str | None):
    """恢复会话历史与槽位；无 session_id 时新建。返回 (sid, history, slots)。"""
    db = get_db()
    sid = session_id or _new_session_id()
    row = db.get_session(sid)
    history: list = []
    slots: dict = {}
    if row:
        try:
            history = json.loads(row["messages_json"]) if row["messages_json"] else []
        except json.JSONDecodeError:
            history = []
        try:
            slots = json.loads(row["slots_json"]) if row["slots_json"] else {}
        except json.JSONDecodeError:
            slots = {}
    return sid, history, slots


class ChatService:
    """对话服务：每次对话一回合。agent 惰性创建（FAQ/转人工路径无需模型）。"""

    def __init__(self, agent=None):
        # agent 参数保留兼容；实际使用按意图路由创建（#1 多 Agent）
        self._agent = agent
        self._router = get_router()

    @staticmethod
    def _route_agent(intent: str) -> str:
        """意图 → 场景 Agent 映射（#1 多 Agent 协作）。"""
        mapping = {
            "product": "presale", "knowledge": "presale", "coupon": "presale",
            "order": "intransit", "logistics": "intransit",
            "refund": "aftersale",
        }
        return mapping.get(intent, "general")

    @property
    def agent(self):
        """兼容属性：通用 Agent（general）。"""
        from agent.react_agent import ReactAgent
        if self._agent is None:
            self._agent = ReactAgent("general")
        return self._agent

    def handle(self, message: str, *, session_id: str | None = None,
               user_id: str = "1001", shop_id: str | None = None) -> ChatResult:
        """处理一回合对话（非流式），返回完整结果。
        :param shop_id: 当前对话商家（shop_a~shop_f；None/ai 为智能客服全店，#F9）"""
        message = (message or "").strip()
        if not message:
            return ChatResult(session_id=session_id or _new_session_id(),
                              reply="请说点什么吧～", intent="chitchat",
                              action="faq", chat_id="")

        sid, history, slots = _restore_session(session_id)
        db = get_db()
        start_ts = time.time()

        history.append({"role": "user", "content": message})

        # ---- 路由分发 ----
        result = self._router.route(message, session_id=sid, user_id=user_id,
                                    history=history)

        if result.action == "escalate":
            reply = result.reply or "已为您转接人工客服。"
            chat_id = chatlog.log_chat(
                session_id=sid, user_id=user_id, query=message,
                intent="escalate", action="escalate", reply=reply,
                escalated=True, ticket_id=result.ticket_id,
                elapsed_ms=int((time.time() - start_ts) * 1000))
            history.append({"role": "assistant", "content": reply, "chat_id": chat_id})
            out = ChatResult(session_id=sid, reply=reply, intent="escalate",
                             action="escalate", chat_id=chat_id,
                             ticket_id=result.ticket_id,
                             elapsed_ms=int((time.time() - start_ts) * 1000))
        elif result.action == "faq":
            reply = result.reply or ""
            chat_id = chatlog.log_chat(
                session_id=sid, user_id=user_id, query=message,
                intent=result.intent, action="faq", reply=reply,
                faq_hit=True, matched=result.matched,
                elapsed_ms=int((time.time() - start_ts) * 1000))
            history.append({"role": "assistant", "content": reply, "chat_id": chat_id})
            out = ChatResult(session_id=sid, reply=reply, intent=result.intent,
                             action="faq", chat_id=chat_id,
                             matched=result.matched,
                             elapsed_ms=int((time.time() - start_ts) * 1000))
        else:  # agent（#1：按意图路由到场景 Agent）
            from agent.react_agent import ReactAgent
            react = ReactAgent(self._route_agent(result.intent))
            reply = self._run_agent(react, message, sid, user_id, history, slots,
                                    intent=result.intent, shop_id=shop_id)
            tool_calls = list(getattr(react, "last_tool_calls", []))
            chat_id = chatlog.log_chat(
                session_id=sid, user_id=user_id, query=message,
                intent=result.intent, action="agent", reply=reply,
                matched=result.matched, tool_calls=tool_calls,
                elapsed_ms=int((time.time() - start_ts) * 1000))
            history.append({"role": "assistant", "content": reply, "chat_id": chat_id})
            slots_out = dict(getattr(react, "last_ctx", {}).get("slots", {}).to_dict()) \
                if hasattr(react, "last_ctx") else {}
            out = ChatResult(session_id=sid, reply=reply, intent=result.intent,
                             action="agent", chat_id=chat_id,
                             slots=slots_out,
                             tool_calls=tool_calls,
                             elapsed_ms=int((time.time() - start_ts) * 1000))

        # 持久化
        db.save_session(sid, user_id, history, out.slots)
        return out

    def _run_agent(self, react, message: str, sid: str, user_id: str,
                   history: list, slots: dict, intent: str | None = None,
                   shop_id: str | None = None) -> str:
        """非流式跑 Agent，收集完整回答（过滤 [思考] 行）。"""
        chunks: list[str] = []
        for chunk in react.execute_stream(
                message, session_id=sid, user_id=user_id,
                slots=slots, history=history[:-1], intent=intent, shop_id=shop_id):
            chunks.append(chunk)
        full_stream = "".join(chunks)
        answer_lines = [ln for ln in full_stream.splitlines() if not ln.startswith("[思考]")]
        return "\n".join(answer_lines).strip() or full_stream.strip()

    def stream(self, message: str, *, session_id: str | None = None,
               user_id: str = "1001", shop_id: str | None = None):
        """
        流式处理一回合对话，逐段产出事件（供 SSE）：
          {"event": "intent", "data": {...}}
          {"event": "token",  "data": "<文本片段>"}
          {"event": "done",   "data": {完整结果}}
          {"event": "error",  "data": {"message": ...}}
        :param shop_id: 当前对话商家（shop_a~shop_f；None/ai 为智能客服全店，#F9）
        """
        message = (message or "").strip()
        if not message:
            yield {"event": "done", "data": json.dumps(
                {"reply": "请说点什么吧～", "intent": "chitchat", "action": "faq",
                 "session_id": session_id or _new_session_id(), "chat_id": ""})}
            return

        sid, history, slots = _restore_session(session_id)
        db = get_db()
        start_ts = time.time()
        history.append({"role": "user", "content": message})

        result = self._router.route(message, session_id=sid, user_id=user_id,
                                    history=history)

        if result.action == "escalate":
            reply = result.reply or "已为您转接人工客服。"
            chat_id = chatlog.log_chat(
                session_id=sid, user_id=user_id, query=message,
                intent="escalate", action="escalate", reply=reply,
                escalated=True, ticket_id=result.ticket_id,
                elapsed_ms=int((time.time() - start_ts) * 1000))
            history.append({"role": "assistant", "content": reply, "chat_id": chat_id})
            db.save_session(sid, user_id, history, {})
            yield {"event": "intent", "data": json.dumps(
                {"intent": "escalate", "action": "escalate", "session_id": sid})}
            yield {"event": "token", "data": reply}
            yield {"event": "done", "data": json.dumps(
                {"reply": reply, "intent": "escalate", "action": "escalate",
                 "session_id": sid, "chat_id": chat_id, "ticket_id": result.ticket_id})}
            return

        if result.action == "faq":
            reply = result.reply or ""
            chat_id = chatlog.log_chat(
                session_id=sid, user_id=user_id, query=message,
                intent=result.intent, action="faq", reply=reply,
                faq_hit=True, matched=result.matched,
                elapsed_ms=int((time.time() - start_ts) * 1000))
            history.append({"role": "assistant", "content": reply, "chat_id": chat_id})
            db.save_session(sid, user_id, history, {})
            yield {"event": "intent", "data": json.dumps(
                {"intent": result.intent, "action": "faq", "session_id": sid})}
            yield {"event": "token", "data": reply}
            yield {"event": "done", "data": json.dumps(
                {"reply": reply, "intent": result.intent, "action": "faq",
                 "session_id": sid, "chat_id": chat_id})}
            return

        # ---- agent 流式（#1：按意图路由到场景 Agent）----
        from agent.react_agent import ReactAgent
        react = ReactAgent(self._route_agent(result.intent))
        yield {"event": "intent", "data": json.dumps(
            {"intent": result.intent, "action": "agent", "session_id": sid,
             "agent": react.agent_type, "shop_id": shop_id})}
        chunks: list[str] = []
        for chunk in react.execute_stream(
                message, session_id=sid, user_id=user_id,
                slots=slots, history=history[:-1], intent=result.intent, shop_id=shop_id):
            chunks.append(chunk)
            yield {"event": "token", "data": chunk}

        # 汇总最终回答（过滤 [思考] 行）
        full_stream = "".join(chunks)
        answer_lines = [ln for ln in full_stream.splitlines() if not ln.startswith("[思考]")]
        final_answer = "\n".join(answer_lines).strip() or full_stream.strip()
        tool_calls = list(getattr(react, "last_tool_calls", []))
        slots_out = {}
        if hasattr(react, "last_ctx"):
            slots_out = react.last_ctx["slots"].to_dict()

        chat_id = chatlog.log_chat(
            session_id=sid, user_id=user_id, query=message,
            intent=result.intent, action="agent", reply=final_answer,
            matched=result.matched, tool_calls=tool_calls,
            elapsed_ms=int((time.time() - start_ts) * 1000))
        history.append({"role": "assistant", "content": final_answer, "chat_id": chat_id})
        db.save_session(sid, user_id, history, slots_out)

        yield {"event": "done", "data": json.dumps(
            {"reply": final_answer, "intent": result.intent, "action": "agent",
             "session_id": sid, "chat_id": chat_id, "tool_calls": tool_calls})}
