"""
RuleCrawl 工业级日志管理中心
支持彩色输出、自动模块命名、统一异常格式化
"""

import logging
import sys
import os
from typing import Optional

# 核心配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s | %(levelname)-1s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class CustomFormatter(logging.Formatter):
    """自定义格式化器，为不同级别添加颜色标识"""
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    blue = "\x1b[34;20m"
    cyan = "\x1b[36;20m"

    FORMATS = {
        logging.DEBUG: grey + LOG_FORMAT + reset,
        logging.INFO: cyan + LOG_FORMAT + reset,
        logging.WARNING: yellow + LOG_FORMAT + reset,
        logging.ERROR: red + LOG_FORMAT + reset,
        logging.CRITICAL: bold_red + LOG_FORMAT + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=DATE_FORMAT)
        return formatter.format(record)

def setup_logging():
    """初始化全局日志系统"""
    root_logger = logging.getLogger()
    
    # 清理已有的 handlers，防止重复打印
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 标准输出 Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(CustomFormatter())
    
    root_logger.addHandler(stdout_handler)
    root_logger.setLevel(LOG_LEVEL)

    # 抑制第三方库的干扰
    for lib in ["httpx", "httpcore", "uvicorn", "motor", "pymongo"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger("app").info(">>> RuleCrawl 统一日志引擎启动成功 [Level: %s] <<<", LOG_LEVEL)

def get_logger(name: Optional[str] = None):
    """
    获取 Logger 实例
    name: 建议传入 __name__，会自动处理为 app.xxx 格式
    """
    if name and name.startswith("app."):
        full_name = name
    elif name:
        full_name = f"app.{name}"
    else:
        full_name = "app"
    return logging.getLogger(full_name)
