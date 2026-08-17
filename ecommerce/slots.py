# -*- coding: utf-8 -*-
"""
槽位状态管理
============
电商客服的"缺什么问什么"机制：每个工具声明所需槽位，调用缺参时
由槽位管理器生成"追问消息"返回给 Agent，Agent 据此向用户提问，
用户补全后再次调用工具。槽位跨轮累积，保存在会话状态中。

槽位表（每个槽位的追问话术）：
  order_id     订单号
  tracking_no  物流单号
  product      商品名
  user_id      用户ID
  reason       售后原因
  new_address  新收货地址
"""
import re

# 工具 → 所需槽位
TOOL_SLOTS = {
    "get_order_info": ["order_id"],
    "get_logistics": ["tracking_no"],
    "get_product_info": ["product"],
    "create_after_sale": ["order_id", "reason"],
    "update_address": ["order_id", "new_address"],
    "query_coupon": ["user_id"],
}

# 槽位 → 追问话术（缺什么问什么）
SLOT_ASK = {
    "order_id": "请提供您的订单号（下单后短信/订单详情页可查）。",
    "tracking_no": "请提供您的物流单号。",
    "product": "请问您想了解哪款商品？可以告诉我商品名称。",
    "user_id": "请提供您的用户ID或登录账号。",
    "reason": "请问您申请售后的原因是什么？例如：不想要了 / 质量问题 / 发错货。",
    "new_address": "请提供新的收货地址（省市区+详细地址）。",
}

# 订单号格式：13位数字（种子数据形如 202608160001 为12位，放宽为>=10位数字）
_ORDER_RE = re.compile(r"^\d{10,20}$")
# 物流单号：字母+数字混合
_TRACKING_RE = re.compile(r"^[A-Za-z0-9]{8,20}$")


class SlotManager:
    """跨轮槽位累积 + 缺参检查。"""

    def __init__(self, slots: dict | None = None):
        self.slots: dict = slots if slots is not None else {}

    def set(self, key: str, value):
        if value is not None and str(value).strip():
            self.slots[key] = str(value).strip()

    def get(self, key: str, default=None):
        return self.slots.get(key, default)

    def update(self, other: dict):
        for k, v in (other or {}).items():
            self.set(k, v)

    def to_dict(self) -> dict:
        return dict(self.slots)

    # ---- 校验 ----
    @staticmethod
    def _valid(key: str, value) -> bool:
        v = str(value or "").strip()
        if not v:
            return False
        if key == "order_id":
            return bool(_ORDER_RE.match(v))
        if key == "tracking_no":
            return bool(_TRACKING_RE.match(v))
        return True

    def missing_slots(self, tool_name: str, args: dict) -> list[str]:
        """返回调用某工具时缺失/非法的槽位列表。"""
        required = TOOL_SLOTS.get(tool_name, [])
        missing = []
        for slot in required:
            # 参数里给的值优先，其次取会话已累积的槽位
            value = args.get(slot) or self.slots.get(slot)
            if not self._valid(slot, value):
                missing.append(slot)
        return missing

    def collect_from_args(self, tool_name: str, args: dict):
        """把本次调用参数中携带的槽位值累积进会话状态。"""
        for slot in TOOL_SLOTS.get(tool_name, []):
            self.set(slot, args.get(slot))

    def ask_message(self, missing_slots: list[str]) -> str:
        """生成给 Agent 的追问消息（Agent 会转述给用户）。"""
        asks = [SLOT_ASK.get(s, f"请补充：{s}。") for s in missing_slots]
        return "【需要补充信息】" + " ".join(asks) + " 请向用户询问获取后再继续。"

    def confirm_tool_call(self, tool_name: str, args: dict) -> str | None:
        """
        写操作二次确认：返回需要回显给用户确认的文案；已确认返回 None。
        约定：args 携带 confirm="yes" 视为用户已确认。
        """
        if str(args.get("confirm", "")).strip().lower() in ("yes", "true", "1", "确认", "是"):
            return None
        if tool_name == "create_after_sale":
            return (f"【等待用户确认】用户申请售后：订单号 {args.get('order_id')}，"
                    f"原因：{args.get('reason')}。请向用户回显并确认「确认申请退款/退货？」后再次调用（confirm=yes）。")
        if tool_name == "update_address":
            return (f"【等待用户确认】用户修改收货地址：订单号 {args.get('order_id')}，"
                    f"新地址：{args.get('new_address')}。请向用户回显并确认后再次调用（confirm=yes）。")
        return None
