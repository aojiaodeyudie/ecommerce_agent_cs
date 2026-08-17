# -*- coding: utf-8 -*-
"""
意图分类器
==========
阶段二：意图路由的核心。将用户输入分类为 10 类意图，供路由分发使用。

设计：
  - BaseIntentClassifier 抽象基类：预留 LLM 分类接口（后续迭代切换）；
  - RuleIntentClassifier：关键词 + 正则规则实现，零成本、可解释、稳定可控；
  - 优先级：escalate > refund > logistics > order > coupon > policy > faq
            > product > knowledge > chitchat（兜底）；
  - 特殊规则：订单号/物流单号正则识别。

意图清单：
  escalate   转人工（投诉/负面）
  refund     售后/退换
  logistics  物流查询
  order      订单查询
  coupon     优惠券
  policy     政策（发票/保修）
  faq        高频常见问题（直答）
  product    商品咨询
  knowledge  专业知识（RAG）
  chitchat   闲聊/其他（兜底）
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from utils.config_handler import ecommerce_config
from utils.logger_handler import logger

# 意图定义（顺序即优先级）
INTENT_ORDER = [
    "escalate", "refund", "logistics", "order", "coupon",
    "policy", "faq", "product", "knowledge", "chitchat",
]

# 订单号 / 物流单号 正则（增强规则分类）
_ORDER_NO_RE = re.compile(r"\d{10,20}")
_TRACKING_NO_RE = re.compile(r"[A-Za-z]{1,4}\d{8,16}")


@dataclass
class IntentResult:
    intent: str                       # 意图名
    confidence: float                 # 置信度 0~1
    matched: list[str] = field(default_factory=list)   # 命中的关键词/规则
    method: str = "rule"              # 分类方法：rule / llm


class BaseIntentClassifier(ABC):
    """意图分类器抽象基类：后续接入 LLM 分类时继承此类即可。"""

    @abstractmethod
    def classify(self, text: str) -> IntentResult:
        """对用户输入进行意图分类，返回 IntentResult。"""


class RuleIntentClassifier(BaseIntentClassifier):
    """规则 + 关键词意图分类器。"""

    def __init__(self, rules: dict[str, list[str]] | None = None, order: list[str] | None = None):
        self.rules = rules or ecommerce_config.get("intent_rules", {})
        self.order = order or INTENT_ORDER

    def classify(self, text: str) -> IntentResult:
        t = text.strip()
        if not t:
            return IntentResult(intent="chitchat", confidence=0.1, matched=[])

        # 0) 正则：订单号 / 物流单号 强特征
        has_order_no = bool(_ORDER_NO_RE.search(t))
        has_tracking = bool(_TRACKING_NO_RE.search(t))
        if has_tracking and any(k in t for k in ("快递", "物流", "运单", "到哪")):
            return IntentResult(intent="logistics", confidence=0.95,
                                matched=["物流单号识别"], method="rule+regex")
        # 带订单号的售后请求 → refund（而非 order）
        if has_order_no and any(k in t for k in ("退", "换", "售后", "退款", "退货", "投诉")):
            return IntentResult(intent="refund", confidence=0.92,
                                matched=["订单号+售后词识别"], method="rule+regex")
        if has_order_no and any(k in t for k in ("订单", "单号", "查", "查一下", "发货")):
            return IntentResult(intent="order", confidence=0.9,
                                matched=["订单号识别"], method="rule+regex")

        # 1) 关键词匹配：按优先级顺序，取命中数最多/首个高置信意图
        best_intent, best_hits, best_count = None, [], 0
        for intent in self.order:
            if intent == "chitchat":
                continue
            keywords = self.rules.get(intent, [])
            hits = [kw for kw in keywords if kw in t]
            if hits and len(hits) > best_count:
                best_intent, best_hits, best_count = intent, hits, len(hits)

        if best_intent is None:
            return IntentResult(intent="chitchat", confidence=0.3, matched=[], method="rule")

        # 置信度：命中 1 个 0.7，2 个 0.85，3+ 个 0.95
        conf = min(0.95, 0.6 + 0.15 * best_count)
        return IntentResult(intent=best_intent, confidence=conf, matched=best_hits, method="rule")


class LLMIntentClassifier(BaseIntentClassifier):
    """LLM 意图分类器：调用对话模型做 JSON 分类（qwen3-max）。"""

    # 意图定义说明（喂给 LLM 的分类标准）
    _LABELS = (
        "escalate: 投诉、差评、要求人工、维权、举报、表达强烈不满（负面情绪）\n"
        "refund: 退货、退款、退换、换货、申请售后、取消订单\n"
        "logistics: 物流、快递、配送、签收、运单查询\n"
        "order: 订单查询、发货进度、下单记录\n"
        "coupon: 优惠券、折扣、满减、促销、领券\n"
        "policy: 发票、保修、质保、三包、政策规则\n"
        "faq: 运费、包邮、支付方式、客服时间等通用常见问题\n"
        "product: 商品咨询、价格、参数、规格、推荐、对比\n"
        "knowledge: 使用教程、故障排查、保养、安装等专业知识\n"
        "chitchat: 闲聊、打招呼、与业务无关的内容"
    )

    _PROMPT = (
        "你是电商客服系统的意图分类器。把用户输入分类为以下意图之一，"
        "只输出一个 JSON 对象（不要其他文字）：\n"
        '{"intent": "<意图名>", "reason": "<一句话理由>"}\n\n'
        "意图定义：\n{labels}\n\n用户输入：{text}"
    )

    def __init__(self, model=None):
        self._model = model  # 惰性：None 时用 get_chat_model()

    def classify(self, text: str) -> IntentResult:
        from model.factory import get_chat_model
        model = self._model or get_chat_model()
        prompt = self._PROMPT.format(labels=self._LABELS, text=text)
        resp = model.invoke(prompt)
        content = resp.content if hasattr(resp, "content") else str(resp)
        intent = self._parse_intent(content)
        return IntentResult(intent=intent, confidence=0.9, matched=[], method="llm")

    @staticmethod
    def _parse_intent(content: str) -> str:
        """从模型输出中解析意图名（容错：提取 JSON / 直接匹配意图词）。"""
        if not content:
            return "chitchat"
        # 1) 提取 JSON 中的 intent 字段
        m = re.search(r'\{[^{}]*"intent"\s*:\s*"([^"]+)"[^{}]*\}', content)
        if m:
            intent = m.group(1).strip()
            if intent in set(INTENT_ORDER):
                return intent
        # 2) 输出里直接包含意图名
        for intent in INTENT_ORDER:
            if re.search(rf'\b{intent}\b', content):
                return intent
        return "chitchat"


class HybridIntentClassifier(BaseIntentClassifier):
    """混合分类器：规则高置信直接使用（省钱、稳定）；低置信/模糊场景
    交给 LLM 精分；LLM 失败（无 key/网络异常）自动回退规则结果。"""

    def __init__(self):
        self._rule = RuleIntentClassifier()
        self._llm = None

    def classify(self, text: str) -> IntentResult:
        rule_result = self._rule.classify(text)

        # 规则高置信直接返回（escalate 只要有命中词立即确定，不等 LLM）
        if rule_result.intent == "escalate" and rule_result.matched:
            return rule_result
        if rule_result.confidence >= 0.8:
            return rule_result

        # 低置信 / 闲聊 → LLM 精分（失败回退规则）
        try:
            if self._llm is None:
                self._llm = LLMIntentClassifier()
            return self._llm.classify(text)
        except Exception as e:
            logger.warning(f"[intent]LLM 分类失败，回退规则结果：{e}")
            return rule_result


_CLASSIFIER: BaseIntentClassifier | None = None


def get_classifier() -> BaseIntentClassifier:
    """获取意图分类器单例（按配置选择实现：rule / llm / hybrid）。"""
    global _CLASSIFIER
    if _CLASSIFIER is None:
        ctype = ecommerce_config.get("classifier_type", "hybrid")
        if ctype == "llm":
            _CLASSIFIER = LLMIntentClassifier()
        elif ctype == "hybrid":
            _CLASSIFIER = HybridIntentClassifier()
        else:
            _CLASSIFIER = RuleIntentClassifier()
    return _CLASSIFIER


if __name__ == "__main__":
    clf = get_classifier()
    samples = [
        "X30多少钱",
        "我的订单发货了吗",
        "快递到哪了",
        "有优惠券吗",
        "我要退货",
        "能开发票吗",
        "运费怎么算",
        "机器人老是报错怎么办",
        "我要投诉你们客服",
        "今天天气不错",
    ]
    for s in samples:
        r = clf.classify(s)
        print(f"{s!r:20} -> {r.intent:10} conf={r.confidence:.2f} matched={r.matched}")
