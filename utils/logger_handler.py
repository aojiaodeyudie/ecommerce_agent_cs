"""
日志处理模块
"""
import logging
import os
from typing import Optional
from utils.path_tool import get_abs_path
from datetime import datetime

# 日志保存根目录
LOG_ROOT = get_abs_path("logs")

# 获取日志管理器
def get_logger(
        name: str = "agent",
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file: Optional[str] = None
) -> logging.Logger:
    """
    获取日志管理器
    :param name: 日志名称，默认 "agent"
    :param console_level: 控制台日志级别，默认 INFO
    :param file_level: 文件日志级别，默认 DEBUG
    :param log_file: 日志文件路径，为 None 时自动生成
    :return: Logger 实例
    """
    # 确保日志目录存在
    os.makedirs(LOG_ROOT, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # 避免重复添加Handler
    if logger.handlers:
        return logger
    # 日志格式配置
    log_format = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # 控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    # 文件Handler
    if not log_file:
        # 文件名加进程号：避免同秒多次启动/多进程冲突（Windows 文件锁导致 PermissionError）
        log_file = os.path.join(
            LOG_ROOT,
            f"{name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{os.getpid()}.log",
        )

    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except OSError as e:
        # 文件被占用/权限不足时降级为仅控制台输出，避免整个应用崩溃
        logger.warning(f"[logger]无法创建日志文件 {log_file}，降级为仅控制台输出：{e}")
    return logger


# 快捷获取日志管理器
logger = get_logger()

if __name__ == '__main__':
    logger.info("This is an info message")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")



