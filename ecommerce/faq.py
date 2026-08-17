# -*- coding: utf-8 -*-
"""
FAQ 直答服务
============
高频常见问题零成本直答：命中 FAQ 库时直接返回标准答案，
不经过 LLM / Agent（省 token、响应快、答案稳定可审核）。

匹配策略（多级）：
  1. 问题文本精确/包含匹配；
  2. keywords 字段命中（用户输入包含 FAQ 关键词）；
  3. 命中多个候选时取关键词命中数最多的；
  4. 均未命中返回 None，交由下游（Agent / RAG）处理。
"""
from ecommerce.db import get_db
from utils.logger_handler import logger


class FaqService:
    def __init__(self):
        self._db = get_db()

    def lookup(self, text: str) -> str | None:
        """
        查询 FAQ，命中返回答案字符串，未命中返回 None。
        :param text: 用户输入
        """
        text = (text or "").strip()
        if not text:
            return None

        # 1) 完整问题包含匹配（最高优先级）：用户问题直接包含某条 FAQ 问题
        for row in self._db.list_faq():
            if row["question"] in text or text in row["question"]:
                logger.info(f"[faq]精确命中：{row['question']}")
                return row["answer"]

        # 2) 关键词匹配
        candidates = self._db.search_faq(text, limit=3)
        if not candidates:
            return None

        best = candidates[0]
        logger.info(f"[faq]关键词命中：{best['question']}")
        return best["answer"]


_faq_service: FaqService | None = None


def get_faq_service() -> FaqService:
    """FAQ 服务单例。"""
    global _faq_service
    if _faq_service is None:
        _faq_service = FaqService()
    return _faq_service


if __name__ == "__main__":
    svc = get_faq_service()
    samples = [
        "运费怎么算？",
        "包邮吗",
        "什么时候发货",
        "怎么退货啊",
        "能开发票吗",
        "随便聊聊",
    ]
    for s in samples:
        ans = svc.lookup(s)
        print(f"{s!r:16} -> {'命中: ' + ans[:40] if ans else '未命中'}")
