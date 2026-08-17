# -*- coding: utf-8 -*-
"""
业务查询 API：商品 / 订单 / 物流 / 优惠券 / 退换政策
封装 ecommerce/db.py，供第三方系统/前端直接查询。
"""
import json

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CouponOut, LogisticsOut, OrderOut, PolicyOut, ProductOut,
)
from ecommerce.db import get_db

router = APIRouter(prefix="/api", tags=["business"])

db = get_db()


@router.get("/products", response_model=list[ProductOut], summary="商品查询")
def list_products(name: str | None = None):
    """按名称模糊查询商品；不传 name 返回全部。"""
    if name:
        row = db.get_product_by_name(name)
        rows = [row] if row else []
    else:
        rows = db.list_products(limit=50)
    out = []
    for r in rows:
        try:
            specs = json.loads(r["specs"]) if r["specs"] else {}
        except json.JSONDecodeError:
            specs = {}
        out.append(ProductOut(
            product_id=r["product_id"], name=r["name"], category=r["category"],
            price=r["price"], specs=specs, stock=r["stock"],
            description=r["description"] or "",
        ))
    return out


@router.get("/orders/{order_id}", response_model=OrderOut, summary="订单查询")
def get_order(order_id: str):
    row = db.get_order(order_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return OrderOut(
        order_id=row["order_id"], user_id=row["user_id"], product_id=row["product_id"],
        quantity=row["quantity"], amount=row["amount"], status=row["status"],
        address=row["address"], created_at=row["created_at"],
    )


@router.get("/logistics/{tracking_no}", response_model=LogisticsOut, summary="物流查询")
def get_logistics(tracking_no: str):
    row = db.get_logistics(tracking_no)
    if row is None:
        raise HTTPException(status_code=404, detail=f"物流单 {tracking_no} 不存在")
    try:
        trace = json.loads(row["trace_json"]) if row["trace_json"] else []
    except json.JSONDecodeError:
        trace = []
    return LogisticsOut(
        tracking_no=row["tracking_no"], order_id=row["order_id"],
        carrier=row["carrier"], status=row["status"], trace=trace,
    )


@router.get("/coupons/{user_id}", response_model=list[CouponOut], summary="优惠券查询")
def get_coupons(user_id: str):
    rows = db.list_coupons_by_user(user_id)
    return [CouponOut(
        coupon_id=r["coupon_id"], user_id=r["user_id"], title=r["title"],
        threshold=r["threshold"], discount=r["discount"], expire_at=r["expire_at"],
    ) for r in rows]


@router.get("/refund-policy", response_model=PolicyOut, summary="退换政策查询")
def get_refund_policy(category: str = "default"):
    from ecommerce.tools import check_refund_policy
    policy = check_refund_policy.invoke({"category": category})
    return PolicyOut(category=category, policy=policy)
