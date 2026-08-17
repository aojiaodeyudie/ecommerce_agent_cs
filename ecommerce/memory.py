# -*- coding: utf-8 -*-
"""
多轮记忆管理
============
把会话历史接入 Agent 上下文（阶段一 Agent 只看当前单轮，历史仅 UI 展示）。

策略：
  - 滑动窗口：最近 max_messages 条完整进入 Agent 上下文（保证质量）；
  - 窗口外老消息：当前按丢弃处理（规则版）；预留 summarize_old()
    接口，后续可接入 LLM 摘要压缩，不丢关键信息。
"""
from langchain_core.messages import HumanMessage, AIMessage

from utils.config_handler import ecommerce_config

DEFAULT_MAX_MESSAGES = 20


def build_context_messages(history: list[dict] | None, max_messages: int | None = None) -> list:
    """
    从会话历史构建 Agent 上下文消息序列（滑动窗口）。
    :param history: [{"role": "user"|"assistant", "content": str}, ...]
    :param max_messages: 窗口大小，默认取配置（memory.max_messages），
                         未配置用 DEFAULT_MAX_MESSAGES
    """
    history = history or []
    if max_messages is None:
        max_messages = ecommerce_config.get("memory", {}).get("max_messages", DEFAULT_MAX_MESSAGES)

    recent = history[-max_messages:] if len(history) > max_messages else history

    messages = []
    for m in recent:
        role = m.get("role")
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def summarize_old(history: list[dict], max_messages: int = DEFAULT_MAX_MESSAGES) -> str | None:
    """
    预留接口：对窗口外的老消息生成摘要（LLM 压缩）。
    阶段二暂不启用（避免每次对话都额外调模型）；后续接入：
      from model.factory import get_chat_model
      ... 调用模型把老消息压缩为一段摘要，作为 SystemMessage 注入 ...
    """
    if len(history) <= max_messages:
        return None
    return None
