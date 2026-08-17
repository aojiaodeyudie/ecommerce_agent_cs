# -*- coding: utf-8 -*-
"""
API 请求/响应模型（Pydantic）
============================
FastAPI 自动校验请求参数并生成 OpenAPI 文档（/docs）。
"""
from pydantic import BaseModel, Field


# ---------------------------------------------------------------- chat

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")
    session_id: str | None = Field(None, description="会话ID（续聊时传，缺省自动生成）")
    user_id: str = Field("1001", description="用户ID（真实场景由登录态注入）")
    shop_id: str | None = Field(None, description="对话商家（shop_a~shop_f；缺省为智能客服全店，#F9）")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    action: str          # escalate | faq | agent
    chat_id: str
    ticket_id: str | None = None
    tool_calls: list = []
    elapsed_ms: int = 0


class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待分类文本")


class IntentResponse(BaseModel):
    intent: str
    confidence: float
    matched: list = []


# ---------------------------------------------------------------- business

class ProductOut(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    specs: dict
    stock: int
    description: str = ""


class OrderOut(BaseModel):
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    amount: float
    status: str
    address: str
    created_at: str


class LogisticsOut(BaseModel):
    tracking_no: str
    order_id: str
    carrier: str
    status: str
    trace: list


class CouponOut(BaseModel):
    coupon_id: str
    user_id: str
    title: str
    threshold: float
    discount: float
    expire_at: str


class PolicyOut(BaseModel):
    category: str
    policy: str


# ---------------------------------------------------------------- ops

class TicketOut(BaseModel):
    ticket_id: str
    session_id: str | None
    user_id: str | None
    reason: str
    status: str
    transcript: list
    created_at: str


class StatsOut(BaseModel):
    total: int
    intent_dist: dict
    action_dist: dict
    escalate_rate: float
    faq_hit_rate: float
    tool_calls: int
    # 星级评价统计（#E4）
    rated_count: int = 0
    bad_count: int = 0
    bad_rate: float = 0.0
    star_dist: dict = {}
    solved_dist: dict = {}


class BadRatingOut(BaseModel):
    """1-3 星差评记录（#E4：运营端坐席台展示）。"""
    chat_id: str
    ts: str
    session_id: str | None = None
    user_id: str | None = None
    query: str = ""
    intent: str = ""
    rating: int
    solved: str | None = None
    reason: str | None = None
    reply: str | None = None
    # #E5：坐席回复
    rating_reply: str | None = None
    rating_replied_at: str | None = None


class BadcaseOut(BaseModel):
    escalations: list
    faq_misses: list
    empty_replies: list


class FaqIn(BaseModel):
    question: str = Field(..., min_length=2, description="问题")
    answer: str = Field(..., min_length=2, description="答案")
    keywords: str = Field("", description="命中关键词，逗号分隔")
    category: str = Field("general", description="分类")


class FaqOut(BaseModel):
    id: int
    question: str
    answer: str
    keywords: str = ""
    category: str = "general"
