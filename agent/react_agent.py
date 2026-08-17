# -*- coding: utf-8 -*-
"""
电商智能客服 Agent 工厂（#1 多 Agent 协作）
============================================
按意图将用户分流到最聚焦的场景 Agent，降低工具选择错误率：

  presale    售前   （product / knowledge / coupon 未命中 FAQ）
            工具：get_product_info, search_knowledge_base, query_coupon
  intransit  售中   （order / logistics）
            工具：get_order_info, get_logistics, update_address
  aftersale  售后   （refund）
            工具：get_order_info, create_after_sale, check_refund_policy
  general    通用   （chitchat 及其他兜底，保留全 9 工具）

- get_agent(agent_type)：惰性创建并缓存（避免无 key 时 import 即崩）；
- 槽位（SlotManager）在运行时 context 中，跨 Agent 天然共享（同一会话切换场景不丢上下文）；
- 中间件（槽位追问/二次确认/转人工注入/日志）对所有 Agent 一致。
"""
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk

from model.factory import get_chat_model
from utils.prompt_loader import (
    load_system_prompt, load_presale_prompt, load_intransit_prompt, load_aftersale_prompt,
)
from ecommerce.tools import (
    get_product_info, get_order_info, get_logistics, query_coupon,
    check_refund_policy, create_after_sale, update_address,
    escalate_to_human, search_knowledge_base,
)
from ecommerce.slots import SlotManager
from ecommerce.memory import build_context_messages
from agent.tools.middleware import shop_prompt_switch, log_before_model, monitor_tool

# ---------------------------------------------------------------- 场景规格

_PRESALE_TOOLS = [get_product_info, search_knowledge_base, query_coupon]
_INTRANSIT_TOOLS = [get_order_info, get_logistics, update_address]
_AFTERSALE_TOOLS = [get_order_info, create_after_sale, check_refund_policy]
_GENERAL_TOOLS = [
    get_product_info, get_order_info, get_logistics, query_coupon,
    check_refund_policy, create_after_sale, update_address,
    escalate_to_human, search_knowledge_base,
]

# agent_type -> (tools, prompt_loader)
AGENT_SPECS: dict[str, tuple[list, callable]] = {
    "presale": (_PRESALE_TOOLS, load_presale_prompt),
    "intransit": (_INTRANSIT_TOOLS, load_intransit_prompt),
    "aftersale": (_AFTERSALE_TOOLS, load_aftersale_prompt),
    "general": (_GENERAL_TOOLS, load_system_prompt),
}

_AGENTS: dict[str, object] = {}


def get_agent(agent_type: str = "general"):
    """获取（惰性创建并缓存）指定场景的 Agent。未知类型回退 general。"""
    key = agent_type if agent_type in AGENT_SPECS else "general"
    if key not in _AGENTS:
        tools, prompt_loader = AGENT_SPECS[key]
        _AGENTS[key] = create_agent(
            model=get_chat_model(),
            system_prompt=prompt_loader(),
            tools=tools,
            middleware=[shop_prompt_switch, log_before_model, monitor_tool],
        )
    return _AGENTS[key]


def reset_agents():
    """清空 Agent 缓存（测试/热重载用）。"""
    _AGENTS.clear()


# ---------------------------------------------------------------- 执行包装

class ReactAgent:
    """单个场景 Agent 的流式执行包装（轻量，内部引用缓存的图）。"""

    def __init__(self, agent_type: str = "general"):
        self.agent_type = agent_type
        self.agent = get_agent(agent_type)

    def execute_stream(self, query, *, session_id=None, user_id=None, slots=None,
                       history=None, intent=None, shop_id=None):
        """
        流式执行一次用户提问。
        :param session_id: 会话ID（用于会话持久化）
        :param user_id: 用户ID（登录态注入，不再随机）
        :param slots: 会话已累积的槽位（order_id/商品名等）
        :param history: 会话历史（不含当前问题），接入 Agent 多轮上下文
        :param intent: 路由识别的意图，注入运行时上下文
        :param shop_id: 当前对话商家（shop_a~shop_f；ai/None 为智能客服全店兜底，#F9）
        """
        # 多轮上下文：历史（滑动窗口）+ 当前问题
        context_messages = build_context_messages(history or [])
        input_dict = {
            "messages": context_messages + [{"role": "user", "content": query}],
        }
        # 运行时上下文：中间件通过 request.runtime.context 读取
        ctx = {
            "session_id": session_id,
            "user_id": user_id,
            "shop_id": shop_id,
            "slots": SlotManager(slots or {}),
            "messages": (history or []) + [{"role": "user", "content": query}],
            "intent": intent,
        }
        self.last_tool_calls: list[str] = []
        # stream_mode="messages"：真正的 token 级流式（"values" 模式只在节点完成后
        # 一次性输出完整消息，模型回答非流式，且会把用户消息回显出去）
        for chunk, _metadata in self.agent.stream(input_dict, stream_mode="messages", context=ctx):
            # 只处理 AI 消息的增量块（注意：chunk.type 是类名 "AIMessageChunk"，用 isinstance 判断）
            if not isinstance(chunk, AIMessageChunk):
                continue

            # 工具调用增量（tool_call_chunks 是分片，name 只在首个分片携带）
            tool_chunks = getattr(chunk, "tool_call_chunks", None) or []
            for tc in tool_chunks:
                name = tc.get("name")
                if name:
                    self.last_tool_calls.append(name)
                    yield f"[思考] 调用 {name}...\n"

            # 文本增量（AIMessageChunk.content，可能是字符串或多模态片段列表）
            content = chunk.content
            if isinstance(content, list):
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            else:
                text = str(content or "")
            if text:
                yield text
        # 记录本轮执行后的运行上下文（含累积的槽位），供上层取回持久化
        self.last_ctx = ctx


if __name__ == '__main__':
    for at in AGENT_SPECS:
        agent = ReactAgent(at)
        print(f"[{at}] 就绪，工具: {[t.name for t in AGENT_SPECS[at][0]]}")
