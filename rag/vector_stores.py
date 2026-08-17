# -*- coding: utf-8 -*-
"""
向量库服务（分域版，阶段二）
============================
按域（domain）管理多个 Chroma collection：
  - 每个域独立 collection、独立数据目录、独立检索 k 值、独立 MD5 去重文件；
  - 兼容旧单库模式（domain 缺省时用默认 collection）；
  - 域配置见 config/chroma.yml 的 domains 段。

用法：
  vs = VectorStoreService(domain="manual")
  vs.load_document()                 # 灌入该域数据目录下的文档
  retriever = vs.get_retriever()     # 该域检索器
"""
import os.path

from utils.logger_handler import logger
from langchain_core.documents import Document
from utils.path_tool import get_abs_path
from langchain_chroma import Chroma
from utils.config_handler import chroma_config
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from model.factory import get_embedding_model

# 默认单库模式（兼容旧数据）
_DEFAULT_COLLECTION = chroma_config["collection_name"]


def _domain_config(domain: str | None) -> dict:
    """返回域的配置：collection 名 / 数据目录 / k 值 / md5 文件。"""
    domains = chroma_config.get("domains", {})
    if domain and domain in domains:
        cfg = domains[domain]
        md5_file = f"{chroma_config['md5_hex_store'].rsplit('.', 1)[0]}_{domain}.text"
        return {
            "collection": cfg.get("collection", f"kb_{domain}"),
            "data_path": cfg.get("data_path", f"data/kb/{domain}"),
            "k": cfg.get("k", chroma_config["k"]),
            "md5_file": md5_file,
        }
    # 单库模式
    return {
        "collection": _DEFAULT_COLLECTION,
        "data_path": chroma_config["data_path"],
        "k": chroma_config["k"],
        "md5_file": chroma_config["md5_hex_store"],
    }


class VectorStoreService:
    def __init__(self, domain: str | None = None):
        """domain: 知识域（manual 等）；None 表示默认单库。"""
        self.domain = domain
        cfg = _domain_config(domain)
        self.collection_name = cfg["collection"]
        self.data_path = cfg["data_path"]
        self.k = cfg["k"]
        self.md5_file = cfg["md5_file"]

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=get_embedding_model(),
            persist_directory=get_abs_path(chroma_config["persist_directory"]),
        )
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config["chunk_size"],
            chunk_overlap=chroma_config["chunk_overlap"],
            separators=chroma_config["separators"],
            length_function=len,
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": self.k})

    def similarity_search_with_scores(self, query: str, k: int | None = None):
        """
        带相关性分数的相似检索（供 RAG 服务做阈值过滤）。
        :return: [(Document, relevance_score)]，score 为 0~1，越大越相关。
        """
        return self.vector_store.similarity_search_with_relevance_scores(
            query, k=k or self.k
        )

    def load_document(self):
        """
        从本域数据目录读取数据文件，转为向量存入对应 collection。
        文件 MD5 去重（每个域独立 md5 文件）。
        """
        def check_md5_hex(md5_for_check: str):
            md5_path = get_abs_path(self.md5_file)
            if not os.path.exists(md5_path):
                open(md5_path, "w").close()
                return False
            with open(md5_path, "r") as f:
                for line in f:
                    if line.strip() == md5_for_check:
                        return True
                return False

        def save_md5_hex(md5_hex: str):
            with open(get_abs_path(self.md5_file), "a", encoding="utf-8") as f:
                f.write(md5_hex + "\n")

        def get_file_document(read_path: str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            elif read_path.endswith(".pdf"):
                return pdf_loader(read_path)
            return []

        allowed_file_path: list[str] = listdir_with_allowed_type(
            get_abs_path(self.data_path),
            tuple(chroma_config["allow_konwledge_file_type"]),
        )
        for path in allowed_file_path:
            file_md5_hex = get_file_md5_hex(path)
            if check_md5_hex(file_md5_hex):
                logger.info(f"[加载知识库][{self.collection_name}]{path} 已存在，跳过")
                continue
            try:
                documents: list[Document] = get_file_document(path)
                if not documents:
                    logger.info(f"[加载知识库][{self.collection_name}]{path} 无有效文本，跳过")
                    continue
                split_document: list[Document] = self.spliter.split_documents(documents)
                if not split_document:
                    logger.info(f"[加载知识库][{self.collection_name}]{path} 分片后无内容，跳过")
                    continue
                self.vector_store.add_documents(split_document)
                save_md5_hex(file_md5_hex)
                logger.info(f"[加载知识库][{self.collection_name}]{path} 内容添加成功")
            except Exception as e:
                logger.error(f"[加载知识库][{self.collection_name}]{path} 加载失败: {str(e)}", exc_info=True)


if __name__ == '__main__':
    # 灌库：按域逐个执行（需要 DASHSCOPE_API_KEY）
    # 用法：python -m rag.vector_stores
    import sys
    domain = sys.argv[1] if len(sys.argv) > 1 else "manual"
    vs = VectorStoreService(domain=domain)
    vs.load_document()
    retriever = vs.get_retriever()
    res = retriever.invoke("扫地机器人迷路了怎么办")
    for r in res:
        print(r.page_content)
        print("=" * 80)
