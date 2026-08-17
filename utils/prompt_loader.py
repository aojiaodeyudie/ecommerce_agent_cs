from utils.config_handler import prompts_config
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def load_system_prompt():
    try:
        system_prompt_path = get_abs_path(prompts_config["main_prompt_path"])
    except Exception as e:
        logger.error(f"[load_system_prompt]在yaml配置中未找到系统提示语路径，请检查配置文件")
        raise e
    try:
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_system_prompt]读取系统提示语文件时出错：{str(e)}，请检查文件路径和权限")
        raise e


def load_rag_prompt():
    try:
        rag_prompt_path = get_abs_path(prompts_config["rag_summarizeprompt_path"])
    except Exception as e:
        logger.error(f"[load_rag_prompt]在yaml配置中未找到RAG提示语路径，请检查配置文件")
        raise e
    try:
        with open(rag_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]读取RAG提示语文件时出错：{str(e)}，请检查文件路径和权限")
        raise e


def _load_scene_prompt(loader_name: str, config_key: str):
    """场景 Agent 提示词加载（#1 多 Agent）：presale / intransit / aftersale。"""
    try:
        prompt_path = get_abs_path(prompts_config[config_key])
    except Exception as e:
        logger.error(f"[{loader_name}]在yaml配置中未找到提示语路径：{config_key}")
        raise e
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[{loader_name}]读取提示语文件时出错：{str(e)}")
        raise e


def load_presale_prompt():
    """售前 Agent 提示词（商品推荐/优惠券/知识库）。"""
    return _load_scene_prompt("load_presale_prompt", "presale_prompt_path")


def load_intransit_prompt():
    """售中 Agent 提示词（订单/物流/改地址）。"""
    return _load_scene_prompt("load_intransit_prompt", "intransit_prompt_path")


def load_aftersale_prompt():
    """售后 Agent 提示词（退换政策/售后申请）。"""
    return _load_scene_prompt("load_aftersale_prompt", "aftersale_prompt_path")
