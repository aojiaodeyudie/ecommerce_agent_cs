# -*- coding: utf-8 -*-
"""
中间件层：工具监控 / 槽位追问 / 二次确认 / 转人工注入 / 商家身份注入
==================================================================
在原有日志监控基础上，叠加电商客服的交互机制：
  1. monitor_tool（wrap_tool_call）
     - 日志（原有）
     - 槽位累积 + 缺参追问（缺什么问什么）
     - 自动注入 user_id（query_coupon）
     - #F9 自动注入 shop_id（get_product_info 按商家过滤）
     - #F9 知识检索按当前商家域（search_knowledge_base）
     - 写操作二次确认（create_after_sale / update_address）
     - 转人工前注入会话上下文（session_id/user_id/对话记录）
  2. log_before_model（before_model）：模型调用前日志 + 投诉词检测告警
  3. shop_prompt_switch（dynamic_prompt）：#G2 按当前商家注入客服身份提示词
"""
from typing import Callable

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger

from ecommerce.slots import SlotManager
from ecommerce.shop_profiles import build_shop_system_prompt
from utils.config_handler import ecommerce_config

# 需要二次确认的写操作工具
_CONFIRM_TOOLS = set(ecommerce_config.get("confirm_required_tools", []))
# 投诉/负面触发词
_ESCALATE_KEYWORDS = ecommerce_config.get("escalate_keywords", [])


@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """工具调用监控 + 电商交互机制。"""
    ctx = request.runtime.context
    slots: SlotManager = ctx.setdefault("slots", SlotManager())
    tool_name = request.tool_call['name']

    # 保证 args 是可变 dict（langchain 注入的 args 可能是只读映射）
    args = request.tool_call.get('args') or {}
    if not isinstance(args, dict):
        args = dict(args)
        request.tool_call['args'] = args

    logger.info(f"[tool monitor]执行工具：{tool_name}")
    logger.info(f"[tool monitor]传入参数：{args}")

    # 1) 槽位累积：本次参数中携带的槽位值存入会话
    slots.collect_from_args(tool_name, args)

    # 1.5) #F9 自动注入 shop_id（get_product_info 按商家过滤，从会话上下文取）
    if tool_name == "get_product_info" and not str(args.get("shop_id", "")).strip():
        shop = ctx.get("shop_id")
        if shop:
            args["shop_id"] = shop

    # 1.6) #F9 知识检索按当前商家域（search_knowledge_base domain=auto 时注入）
    if tool_name == "search_knowledge_base" and str(args.get("domain", "auto")) == "auto":
        shop = ctx.get("shop_id")
        # 商家对话 → 商家知识域；智能客服(ai/None) → 平台兜底域
        args["domain"] = shop if shop and shop != "ai" else "ai"

    # 2) 自动注入 user_id（query_coupon 场景，从会话上下文取）
    if tool_name == "query_coupon" and not str(args.get("user_id", "")).strip():
        uid = ctx.get("user_id")
        if uid:
            args["user_id"] = uid

    # 3) 缺参检查：缺参数时返回追问消息，不执行工具
    missing = slots.missing_slots(tool_name, args)
    if missing:
        msg = slots.ask_message(missing)
        logger.info(f"[tool monitor]{tool_name} 缺参：{missing}，已生成追问")
        return ToolMessage(content=msg, tool_call_id=request.tool_call['id'])

    # 4) 写操作二次确认：confirm != yes 时返回确认文案，不执行
    if tool_name in _CONFIRM_TOOLS:
        confirm_msg = slots.confirm_tool_call(tool_name, args)
        if confirm_msg:
            logger.info(f"[tool monitor]{tool_name} 等待二次确认")
            return ToolMessage(content=confirm_msg, tool_call_id=request.tool_call['id'])

    # 5) 转人工：#G3 显式把会话上下文写入工具参数（不再用全局变量），
    #    使工单携带完整对话记录，且多用户并发互不干扰
    if tool_name == "escalate_to_human":
        args.setdefault("session_id", ctx.get("session_id"))
        args.setdefault("user_id", ctx.get("user_id"))
        args.setdefault("transcript", ctx.get("messages", []))

    try:
        result = handler(request)
        logger.info(f"[tool monitor]工具{tool_name}调用成功")

        return result
    except Exception as e:
        logger.error(f"工具{tool_name}调用失败，原因：{str(e)}")
        raise e


@before_model
def log_before_model(
        state: AgentState,
        runtime: Runtime,
):
    """模型调用前日志 + 投诉词检测告警。"""
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")

    if state['messages']:
        last_msg = state['messages'][-1]
        logger.debug(f"[log_before_model]{type(last_msg).__name__} | {last_msg.content.strip()}")

        # 投诉词检测：用户消息命中负面词时告警（真正的转人工由 app 层触发）
        if getattr(last_msg, "type", "") == "human":
            content = str(last_msg.content or "")
            hit = [kw for kw in _ESCALATE_KEYWORDS if kw in content]
            if hit:
                logger.warning(f"[投诉检测]用户消息命中负面词：{hit} -> {content[:50]}")

    return None


@dynamic_prompt
def shop_prompt_switch(request: ModelRequest):
    """#G2 按当前对话商家动态注入客服身份提示词。

    - 商家对话（shop_a~shop_f）：把店铺身份/经营范围拼接到基础系统提示词前，
      使 AI 明确"我是哪家店的客服、卖什么"；
    - 智能客服（ai/None）：返回基础系统提示词（平台客服人设）。
    """
    base = ""
    if request.system_message is not None:
        base = request.system_message.content if hasattr(request.system_message, "content") else str(request.system_message)
    if not base and request.messages:
        base = request.messages[0].content if isinstance(request.messages[0].content, str) else str(request.messages[0].content)
    shop_id = request.runtime.context.get("shop_id")
    return build_shop_system_prompt(base, shop_id)
