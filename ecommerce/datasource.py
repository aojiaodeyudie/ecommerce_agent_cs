# -*- coding: utf-8 -*-
"""
数据源适配器抽象（D2）
======================
把"业务数据从哪来"与"客服逻辑"解耦，便于从模拟数据切换到真实业务 API：
  - SqliteDataSource：当前实现（本地模拟数据，开发/演示用）
  - ApiDataSource：真实业务 API 接入点（骨架，按需实现）

接入真实数据源的步骤：
  1. 实现 ApiDataSource 的各方法（调用你的后端服务）；
  2. 在 ecommerce/tools.py 中把数据源实例替换为 ApiDataSource。
客服逻辑（工具/中间件/路由）零改动。
"""
from abc import ABC, abstractmethod


class DataSource(ABC):
    """业务数据源接口（方法签名与 ecommerce/db.py 对齐）。"""

    @abstractmethod
    def get_product_by_name(self, name: str): ...

    @abstractmethod
    def get_order(self, order_id: str): ...

    @abstractmethod
    def get_logistics(self, tracking_no: str): ...

    @abstractmethod
    def list_coupons_by_user(self, user_id: str): ...

    @abstractmethod
    def create_after_sale(self, order_id: str, reason: str): ...

    @abstractmethod
    def update_order_address(self, order_id: str, new_address: str): ...


class SqliteDataSource(DataSource):
    """SQLite 模拟数据源：包装 ecommerce.db。"""

    def __init__(self):
        from ecommerce.db import get_db
        self._db = get_db()

    def get_product_by_name(self, name: str):
        return self._db.get_product_by_name(name)

    def get_order(self, order_id: str):
        return self._db.get_order(order_id)

    def get_logistics(self, tracking_no: str):
        return self._db.get_logistics(tracking_no)

    def list_coupons_by_user(self, user_id: str):
        return self._db.list_coupons_by_user(user_id)

    def create_after_sale(self, order_id: str, reason: str):
        self._db.update_order_status(order_id, "refunding")
        return order_id

    def update_order_address(self, order_id: str, new_address: str):
        self._db.update_order_address(order_id, new_address)
        return order_id


class ApiDataSource(DataSource):
    """真实业务 API 数据源（骨架，待实现）。
    示例（以订单查询为例）：
        def get_order(self, order_id):
            resp = requests.get(
                f"{self.base_url}/orders/{order_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()
    """

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def get_product_by_name(self, name: str):
        raise NotImplementedError("接真实商品服务后实现")

    def get_order(self, order_id: str):
        raise NotImplementedError("接真实订单服务后实现")

    def get_logistics(self, tracking_no: str):
        raise NotImplementedError("接真实物流服务后实现")

    def list_coupons_by_user(self, user_id: str):
        raise NotImplementedError("接真实优惠券服务后实现")

    def create_after_sale(self, order_id: str, reason: str):
        raise NotImplementedError("接真实售后服务后实现")

    def update_order_address(self, order_id: str, new_address: str):
        raise NotImplementedError("接真实订单服务后实现")


# 当前使用的数据源（tools.py 引用；接真实 API 时替换为 ApiDataSource）
_datasource: DataSource | None = None


def get_datasource() -> DataSource:
    global _datasource
    if _datasource is None:
        _datasource = SqliteDataSource()
    return _datasource
