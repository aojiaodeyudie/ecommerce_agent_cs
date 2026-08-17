"""
配置文件处理模块
"""
import yaml
from utils.path_tool import get_abs_path
# 加载RAG配置
def load_rag_config(config_path: str=get_abs_path("config/rag.yml"),encoding:str='utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

# 加载Chroma配置
def load_chroma_config(config_path: str=get_abs_path("config/chroma.yml"),encoding:str='utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

# 加载提示语配置
def load_prompts_config(config_path: str=get_abs_path("config/prompts.yml"),encoding:str='utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

# 加载电商客服配置
def load_ecommerce_config(config_path: str=get_abs_path("config/ecommerce.yml"),encoding:str='utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)

# 加载配置
chroma_config = load_chroma_config()
prompts_config = load_prompts_config()
rag_config = load_rag_config()
ecommerce_config = load_ecommerce_config()

