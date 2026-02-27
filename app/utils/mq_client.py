"""
RuleCrawl RabbitMQ 统一客户端
基于 aio-pika 实现的全局连接池管理
"""

import aio_pika
from typing import Optional
from app.config import RABBITMQ_URL
from app.utils.logger import get_logger

logger = get_logger("utils.mq")

_connection: Optional[aio_pika.RobustConnection] = None

async def init_mq() -> aio_pika.RobustConnection:
    """初始化/获取全局唯一的健壮连接"""
    global _connection
    if _connection is None or _connection.is_closed:
        logger.info("正在建立全局 RabbitMQ 连接...")
        _connection = await aio_pika.connect_robust(RABBITMQ_URL)
        logger.info("RabbitMQ 全局连接建立成功")
    return _connection

async def get_mq_connection() -> aio_pika.RobustConnection:
    """业务层获取连接的唯一入口"""
    return await init_mq()

async def close_mq():
    """优雅关闭全局连接"""
    global _connection
    if _connection:
        await _connection.close()
        _connection = None
        logger.info("RabbitMQ 全局连接已安全关闭")
