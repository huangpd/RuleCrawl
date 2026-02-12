"""
RuleCrawl 数据库连接管理
使用 Motor 异步驱动连接 MongoDB
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)
from app.config import MONGODB_URI, DATABASE_NAME

# 全局客户端实例
client: AsyncIOMotorClient = None
db = None


async def connect_db():
    """连接 MongoDB 数据库"""
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    # 创建索引
    await db.nodes.create_index("project_id")
    await db.tasks.create_index("project_id")
    await db.data_store.create_index("project_id")
    await db.data_store.create_index("task_id")

    logger.info("已连接 MongoDB: %s / %s", MONGODB_URI, DATABASE_NAME)


async def close_db():
    """关闭数据库连接"""
    global client
    if client:
        client.close()
        logger.info("MongoDB 连接已关闭")


def get_db():
    """获取数据库实例"""
    return db
