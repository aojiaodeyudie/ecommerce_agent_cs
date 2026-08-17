# -*- coding: utf-8 -*-
"""
路由分发
========
阶段二核心：把用户输入路由到最合适的处理路径，控制成本与质量。

  escalate（投诉/负面词）  -> 直接转人工建工单（不走 LLM）
  faq（高频常见问题）      -> FAQ 库直答（不走 LLM，省 token、响应快）
  agent（其余意图）        -> 交给 ReAct Agent（工具 + RAG）

FAQ 直答的启用条件（防止误命中）：
  - 意图为 faq / policy / coupon；
  - 或意图为 refund 且用户输入中不含订单号（带订单号的售后请求走 Agent 工具）；
  - order / logistics / product / knowledge / escalate 意图不走 FAQ 直答。
"""
from dataclasses import dataclass, field

from ecommerce.intent import get_classifier, IntentResult
from ecommerce.faq import get_faq_service
from ecommerce.human_handoff import handoff
from utils.config_handler import ecommerce_config
from utils.logger_handler import logger

# 不启用 FAQ 直答的意图（需要走专用工具/流程）
_FAQ_SKIP_INTENTS = {"order", "logistics", "product", "knowledge", "escalate", "chitchat"}

# 允许 FAQ 直答的意图
_FAQ_DIRECT_INTENTS = {"faq", "policy", "coupon"}


@dataclass
class RouteResult:
    action: str                    # escalate | faq | agent
    intent: str                    # 意图名
    confidence: float = 0.0
    matched: list = field(default_factory=list)
    reply: str | None = None       # escalate / faq 的直接回复
    ticket_id: str | None = None   # escalate 的工单号


class Router:
    def __init__(self):
        self.classifier = get_classifier()
        self.faq = get_faq_service()

    def route(self, text: str, *, session_id=None, user_id=None, history=None) -> RouteResult:
        """
        路由分发。
        :param text: 用户输入
        :param session_id / user_id / history: 转人工建工单时携带的会话上下文
        """
        text = (text or "").strip()

        # 1) 投诉/负面词 -> 直接转人工
        escalate_keywords = ecommerce_config.get("escalate_keywords", [])
        hit = [kw for kw in escalate_keywords if kw in text]
        if hit:
            ticket_id = handoff(text, session_id=session_id, user_id=user_id,
                                transcript=history or [])
            reply = (f"非常抱歉给您带来不好的体验🙏 我已为您转接人工客服"
                     f"（工单号：{ticket_id}），专员将尽快接入，请稍候。")
            logger.info(f"[router]投诉词命中 {hit} -> escalate（工单 {ticket_id}）")
            return RouteResult(action="escalate", intent="escalate", confidence=1.0,
                               matched=hit, reply=reply, ticket_id=ticket_id)

        # 2) 意图分类
        ir: IntentResult = self.classifier.classify(text)

        # 3) FAQ 直答（受意图条件约束，防止误命中）
        if ecommerce_config.get("faq_direct_answer", True) and self._faq_allowed(ir, text):
            ans = self.faq.lookup(text)
            if ans:
                logger.info(f"[router]FAQ 直答命中（意图={ir.intent}）")
                return RouteResult(action="faq", intent=ir.intent, confidence=ir.confidence,
                                   matched=ir.matched, reply=ans)

        # 4) 其余 -> Agent
        return RouteResult(action="agent", intent=ir.intent, confidence=ir.confidence,
                           matched=ir.matched)

    @staticmethod
    def _faq_allowed(ir: IntentResult, text: str) -> bool:
        """判断当前意图是否允许 FAQ 直答。"""
        if ir.intent in _FAQ_SKIP_INTENTS:
            return False
        if ir.intent in _FAQ_DIRECT_INTENTS:
            return True
        if ir.intent == "refund":
            # 带订单号的售后请求走 Agent 工具（create_after_sale），不走 FAQ
            import re
            if re.search(r"\d{10,20}", text):
                return False
            return True
        return False


_router: Router | None = None


def get_router() -> Router:
    """路由单例。"""
    global _router
    if _router is None:
        _router = Router()
    return _router


if __name__ == "__main__":
    r = get_router()
    samples = [
        "X30多少钱",                     # agent / product
        "我的订单发货了吗",               # agent / order（FAQ不直答）
        "快递到哪了",                     # agent / logistics
        "有优惠券吗",                     # faq 直答
        "我要退货",                       # faq 直答（refund 无订单号）
        "我要退货 订单202608120001",      # agent / refund（带订单号）
        "能开发票吗",                     # faq 直答
        "运费怎么算",                     # faq 直答
        "机器人老是报错怎么办",            # agent / knowledge
        "我要投诉你们客服",               # escalate
        "今天天气不错",                   # agent / chitchat（FAQ未命中）
    ]
    for s in samples:
        res = r.route(s)
        print(f"{s!r:28} -> {res.action:8} intent={res.intent:10} "
              f"{('回复: ' + res.reply[:30]) if res.reply else ''}")
