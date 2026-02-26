"""
RuleCrawl RabbitMQ 统一客户端
负责全局 MQ 连接池管理
"""

import aio_pika
import logging
from typing import Optional
from app.config import RABBITMQ_URL

logger = logging.getLogger(__name__)

_connection: Optional[aio_pika.RobustConnection] = None

async def init_mq():
    """初始化全局 MQ 连接"""
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(RABBITMQ_URL)
        logger.info("RabbitMQ 连通性校验成功")
    return _connection

async def get_mq_connection() -> aio_pika.RobustConnection:
    """获取全局 MQ 连接"""
    if _connection is None or _connection.is_closed:
        return await init_mq()
    return _connection

async def close_mq():
    """关闭全局 MQ 连接"""
    global _connection
    if _connection:
        await _connection.close()
        logger.info("RabbitMQ 连接已安全释放")
