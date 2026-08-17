# -*- coding: utf-8 -*-
"""
电商客服工具组
==============
替代原 agent_tools.py 的 7 个演示工具，提供电商业务工具。
设计约定：
  - 工具本身只做业务查询/写操作，参数是否齐全、二次确认等由
    中间件层（agent/tools/middleware.py）统一把关；
  - query_coupon 的 user_id 由中间件从会话上下文自动注入；
  - 写操作工具（create_after_sale / update_address）带 confirm
    参数，配合中间件实现"二次确认"；
  - search_knowledge_base 保留原 RAG 能力（知识库问答），惰性初始化。
"""
from langchain_core.tools import tool

from ecommerce.db import get_db
from utils.config_handler import ecommerce_config
from utils.logger_handler import logger

# ---- RAG 惰性初始化（避免无 API key / 无向量库时 import 即崩） ----
_rags: dict = {}


def _get_rag(domain: str = "ai", show_source: bool | None = None):
    """按域缓存 RAG 服务（#F9：ai=智能客服兜底域；shop_a~shop_f=各商家域）。
    #G1 商家场景强制 show_source=False（回答不标注参考来源）。"""
    key = (domain, show_source)
    if key not in _rags:
        from rag.rag_service import RagSummarizeService
        _rags[key] = RagSummarizeService(domain=domain, show_source=show_source)
    return _rags[key]


# 商家知识域列表（#F9：智能客服兜底时按序检索）
_SHOP_DOMAINS = ["shop_a", "shop_b", "shop_c", "shop_d", "shop_e", "shop_f"]


def _rag_summarize_with_fallback(query: str, domain: str) -> str:
    """
    按域检索知识（#F9）：
      - 商家域（shop_a~shop_f）：先查自家域，未命中回退平台兜底域 ai；
      - 平台域（ai）：依次检索全部商家域 + 平台域，取第一个命中，实现"全店可查"。
    """
    def _hit(dom: str, show_source: bool | None = None) -> str | None:
        result = _get_rag(dom, show_source=show_source).rag_summarize(query)
        if result.startswith("抱歉，知识库中没有找到"):
            return None
        return result

    if domain in _SHOP_DOMAINS:
        # 商家域回答不标注参考来源（#G1），回退 ai 域同样不标注
        result = _hit(domain, show_source=False)
        if result is not None:
            return result
        logger.info(f"[rag]商家域 {domain} 未命中，回退智能客服兜底域 ai")
        fallback = _hit("ai", show_source=False)
        return fallback if fallback is not None else _get_rag("ai", show_source=False).rag_summarize(query)

    # ai（平台兜底）：依次检索各商家域，再检索平台域
    for dom in _SHOP_DOMAINS:
        result = _hit(dom)
        if result is not None:
            logger.info(f"[rag]智能客服全店检索命中商家域 {dom}")
            return result
    return _get_rag("ai").rag_summarize(query)


# ---------------------------------------------------------------- 格式化

def _fmt_product(row) -> str:
    import json
    specs = json.loads(row["specs"]) if row["specs"] else {}
    spec_str = "，".join(f"{k}:{v}" for k, v in specs.items())
    return (f"商品：{row['name']}（{row['product_id']}）\n"
            f"品类：{row['category']}  价格：¥{row['price']}  库存：{row['stock']}\n"
            f"核心参数：{spec_str}\n"
            f"简介：{row['description']}")


def _fmt_order(row) -> str:
    return (f"订单号：{row['order_id']}  状态：{row['status']}\n"
            f"金额：¥{row['amount']}（x{row['quantity']}）  下单时间：{row['created_at']}\n"
            f"收货地址：{row['address']}")


def _fmt_logistics(row) -> str:
    import json
    traces = json.loads(row["trace_json"]) if row["trace_json"] else []
    trace_str = "\n".join(f"  {t['time']} {t['location']}：{t['desc']}" for t in traces)
    status_text = {"in_transit": "运输中", "delivered": "已签收", "exception": "异常"}.get(
        row["status"], row["status"])
    return f"物流单号：{row['tracking_no']}  承运商：{row['carrier']}  状态：{status_text}\n物流轨迹：\n{trace_str}"


# ---------------------------------------------------------------- 工具

@tool(description="查询商品信息，入参为商品名称（如\"X30扫地机器人\"），返回商品参数、价格、库存。")
def get_product_info(product: str, shop_id: str = "ai") -> str:
    db = get_db()
    row = db.get_product_by_name(product, shop_id=shop_id)
    if row is None:
        logger.info(f"[get_product_info]未找到商品：{product}（shop={shop_id}）")
        candidates = db.list_products(shop_id=shop_id, limit=10)
        names = "、".join(p['name'] for p in candidates) if candidates else "（本店暂无其他商品）"
        return f"未找到与\"{product}\"相关的商品。可尝试：{names}"
    return _fmt_product(row)


@tool(description="查询订单信息，入参为订单号（纯数字），返回订单状态、金额、收货地址。")
def get_order_info(order_id: str) -> str:
    db = get_db()
    row = db.get_order(order_id)
    if row is None:
        logger.info(f"[get_order_info]未找到订单：{order_id}")
        return f"未查询到订单 {order_id}，请核实订单号是否正确。"
    return _fmt_order(row)


@tool(description="查询物流信息，入参为物流单号（字母数字混合），返回物流轨迹。")
def get_logistics(tracking_no: str) -> str:
    db = get_db()
    row = db.get_logistics(tracking_no)
    if row is None:
        logger.info(f"[get_logistics]未找到物流单：{tracking_no}")
        return f"未查询到物流单 {tracking_no}，请核实物流单号。"
    return _fmt_logistics(row)


@tool(description="查询用户当前可用的优惠券，入参为可选的用户ID（不传则由系统自动识别），返回满减券列表。")
def query_coupon(user_id: str = "") -> str:
    db = get_db()
    uid = user_id.strip()
    if not uid:
        return "【需要补充信息】未能识别当前用户，请先获取用户身份后再查询优惠券。"
    rows = db.list_coupons_by_user(uid)
    if not rows:
        return f"用户{uid}当前没有可用优惠券。"
    items = "；".join(
        f"{r['title']}（满{r['threshold']}减{r['discount']}，{r['expire_at']}到期）" for r in rows)
    return f"用户{uid}的可用优惠券：{items}"


@tool(description="查询退换货政策，入参为商品品类（electronics/consumables/扫地机器人等），返回退换规则。")
def check_refund_policy(category: str) -> str:
    policy = ecommerce_config.get("refund_policy", {})
    # 品类匹配：优先精确，其次按关键词
    cat = category.strip()
    if cat in policy:
        return policy[cat]
    if any(k in cat for k in ("电子", "机器人", "吸尘", "净化", "锁", "家电")):
        return policy.get("electronics", policy.get("default", ""))
    if any(k in cat for k in ("耗材", "滤网", "尘盒", "边刷", "刷")):
        return policy.get("consumables", policy.get("default", ""))
    return policy.get("default", "")


@tool(description="发起售后申请（退款/退货/换货），入参为订单号和原因；写操作，需用户二次确认后携带confirm='yes'再次调用。")
def create_after_sale(order_id: str, reason: str, confirm: str = "no") -> str:
    db = get_db()
    order = db.get_order(order_id)
    if order is None:
        return f"未找到订单 {order_id}，请核实订单号。"
    db.update_order_status(order_id, "refunding")
    logger.info(f"[create_after_sale]订单{order_id}已进入售后流程，原因：{reason}")
    return (f"售后申请已受理：订单 {order_id}（{order['product_id']}）已进入退款/退货处理流程，"
            f"原因：{reason}。退款将在1-3个工作日原路退回，请留意到账通知。")


@tool(description="修改订单收货地址，入参为订单号和新地址；写操作，需用户二次确认后携带confirm='yes'再次调用。")
def update_address(order_id: str, new_address: str, confirm: str = "no") -> str:
    db = get_db()
    order = db.get_order(order_id)
    if order is None:
        return f"未找到订单 {order_id}，请核实订单号。"
    if order["status"] in ("shipped", "delivered"):
        return f"订单 {order_id} 已发货，无法修改地址，建议联系人工客服处理。"
    db.update_order_address(order_id, new_address)
    logger.info(f"[update_address]订单{order_id}地址已修改为：{new_address}")
    return f"订单 {order_id} 的收货地址已修改为：{new_address}"


@tool(description="转人工客服，入参为原因，会创建工单并交由人工坐席处理。")
def escalate_to_human(reason: str, session_id: str = None, user_id: str = None,
                      transcript: list = None) -> str:
    # #G3 会话上下文由中间件显式注入（不再依赖全局变量），工单携带完整对话记录
    from ecommerce.human_handoff import handoff
    ticket_id = handoff(reason, session_id=session_id, user_id=user_id,
                        transcript=transcript)
    return (f"已为您转接人工客服（工单号：{ticket_id}），"
            f"转接原因：{reason}。人工专员将尽快接入，请您稍候。")


@tool(description="从知识库检索商品使用/故障排查/保养/选购等专业资料，入参为检索词query（可不传domain，系统自动按当前店铺检索，未命中会回退平台知识库）。")
def search_knowledge_base(query: str, domain: str = "auto") -> str:
    """
    #F9 按当前对话店铺检索知识：
      - domain 显式指定时（ai/shop_a~shop_f）用指定域；
      - 默认 auto：由中间件注入当前 shop_id 对应的知识域；
      - 商家域未命中回退智能客服兜底域。
    """
    if domain and domain != "auto":
        return _get_rag(domain).rag_summarize(query)
    # auto：由中间件从上下文注入实际域（见 agent/tools/middleware.py）
    return _rag_summarize_with_fallback(query, "ai")
