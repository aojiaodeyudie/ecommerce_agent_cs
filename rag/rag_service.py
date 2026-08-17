"""
RAG 总结服务（A2 增强版）
=========================
用户提问 → 检索带相关性分数的参考资料 → 阈值过滤低相关文档 →
拼接上下文（含来源出处）→ 提交模型生成总结回答。

增强点：
  - 相关性阈值过滤：低于 score_threshold 的文档不喂给模型（防噪声）；
  - 引用出处：上下文携带来源（source metadata），prompt 要求回答标注参考来源；
  - 全部被过滤时返回明确提示（引导转人工），而非编造回答。
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from rag.vector_stores import VectorStoreService
from utils.config_handler import chroma_config
from utils.prompt_loader import load_rag_prompt
from model.factory import get_chat_model


class RagSummarizeService(object):
    def __init__(self, domain: str | None = "manual", show_source: bool | None = None):
        """
        :param domain: 知识域（对应 chroma.yml domains 配置），
                       None 表示默认单库；阶段二默认使用 manual 域。
        :param show_source: 回答是否标注参考来源（#G1）；商家域默认 False（不标注），
                           其余域默认 True（平台可追溯）。
        """
        self.domain = domain
        self.vector_store = VectorStoreService(domain=domain)
        # 相关性阈值：低于该值的检索结果视为不相关，不进入上下文
        self.score_threshold = chroma_config.get("score_threshold", 0.35)
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = get_chat_model()
        self.chain = self.prompt_template | self.model | StrOutputParser()
        # #G1 商家域回答不标注参考来源
        if show_source is None:
            show_source = not domain.startswith("shop_")
        self.show_source = show_source

    # 搜索参考资料：带相关性分数并过滤
    def retriever_docs(self, query: str) -> list[tuple[Document, float]]:
        """返回 (文档, 相关性分数) 列表，已过滤低于阈值的文档。"""
        docs_with_scores = self.vector_store.similarity_search_with_scores(query)
        filtered = [(doc, score) for doc, score in docs_with_scores
                    if score is not None and score >= self.score_threshold]
        return filtered

    # 根据问题生成总结
    def rag_summarize(self, query: str) -> str:
        results = self.retriever_docs(query)
        if not results:
            return ("抱歉，知识库中没有找到与该问题直接相关的资料。"
                    "建议您转人工客服进一步咨询（回复\"转人工\"即可）。")

        context = ""
        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "未知来源")
            context += (
                f"【参考资料{i}】来源:{source} | 相关度:{score:.2f}\n"
                f"内容:{doc.page_content}\n"
            )

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
                "show_source": str(self.show_source).lower(),
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合那些扫地机器人"))
