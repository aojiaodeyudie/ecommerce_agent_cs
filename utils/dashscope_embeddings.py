"""
自定义 DashScope Embeddings，使用 OpenAI 兼容 HTTP 接口直接调用
避免 langchain-dashscope 与新版 langchain-core 的 pydantic_v1 兼容性问题
"""
import os
import requests
from langchain_core.embeddings import Embeddings


class DashScopeEmbeddings(Embeddings):
    def __init__(self, model: str):
        self.model = model
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """调用 DashScope Embedding API，返回向量列表"""
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "input": [str(t) for t in texts],
                "dimensions": 1024
            }
        )
        data = resp.json()
        if resp.status_code == 200 and "data" in data:
            return [item["embedding"] for item in data["data"]]
        raise Exception(f"DashScope Embedding 请求失败: {data}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入文档，每批最多10条"""
        all_embeddings = []
        for i in range(0, len(texts), 10):
            batch = texts[i:i + 10]
            all_embeddings.extend(self._call_api(batch))
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """嵌入单条查询文本"""
        return self._call_api([text])[0]
