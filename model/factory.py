# -*- coding: utf-8 -*-
"""
模型工厂：Chat 模型 / Embedding 模型（惰性单例）
==================================================
- 顶层不再立即构造模型（避免 import 即崩溃）；
- 通过 get_chat_model() / get_embedding_model() 惰性创建并缓存；
- 缺少 DASHSCOPE_API_KEY 时抛出带清晰中文指引的异常。
"""
import os
from abc import ABC, abstractmethod
from typing import Optional, Union

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from utils.dashscope_embeddings import DashScopeEmbeddings
from utils.config_handler import rag_config
from utils.path_tool import get_abs_path

_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _load_env_file():
    """从项目根 .env 加载环境变量（C1）。未安装 python-dotenv 时静默跳过，
    仍可用系统环境变量方式设置 DASHSCOPE_API_KEY。"""
    try:
        from dotenv import load_dotenv
        load_dotenv(get_abs_path(".env"))
    except ImportError:
        pass


def _require_api_key() -> str:
    _load_env_file()
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "未检测到 DASHSCOPE_API_KEY，无法创建模型。请二选一配置：\n"
            "  方式一（推荐）：在项目根目录创建 .env 文件（参考 .env.example），"
            "填写 DASHSCOPE_API_KEY=你的key\n"
            "  方式二：设置系统环境变量\n"
            "    Windows PowerShell:  $env:DASHSCOPE_API_KEY = \"你的key\"\n"
            "    macOS / Linux:       export DASHSCOPE_API_KEY=你的key\n"
            "获取方式：阿里云百炼控制台 -> API-KEY 管理。"
        )
    return key


class BaseModelFactory(ABC):
    @abstractmethod
    def generate(self) -> Optional[Union[Embeddings, BaseChatModel]]:
        pass


class EmbeddingFactory(BaseModelFactory):
    def generate(self) -> Optional[Embeddings]:
        return DashScopeEmbeddings(
            model=rag_config["embedding_model_name"],
        )


class ChatModelFactory(BaseModelFactory):
    def generate(self) -> Optional[BaseChatModel]:
        return ChatOpenAI(
            api_key=_require_api_key(),
            model=rag_config["chat_model_name"],
            base_url=_DASHSCOPE_BASE_URL,
        )


# ---- 惰性单例 ----
_chat_model: Optional[BaseChatModel] = None
_embedding_model: Optional[Embeddings] = None


def get_chat_model() -> BaseChatModel:
    """获取 Chat 模型（首次调用时创建，带 API key 校验）。"""
    global _chat_model
    if _chat_model is None:
        _chat_model = ChatModelFactory().generate()
    return _chat_model


def get_embedding_model() -> Embeddings:
    """获取 Embedding 模型（首次调用时创建）。"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingFactory().generate()
    return _embedding_model
