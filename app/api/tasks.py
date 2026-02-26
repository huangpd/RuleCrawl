"""
任务管理 API - 分布式版
基于 RabbitMQ 广播信号实现任务控制
"""

import uuid
import json
import aio_pika
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.database import get_db
from app.engine.flow_manager import FlowManager
from app.utils.logger import get_logger
from app.utils.mq_client import get_mq_connection

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["任务管理"])

@router.post("/projects/{project_id}/run")
async def run_project(project_id: str, background_tasks: BackgroundTasks):
    """启动爬虫任务"""
    db = get_db()
    project = await db.projects.find_one({"_id": project_id})
    if not project: raise HTTPException(status_code=404, detail="项目不存在")

    task_id = str(uuid.uuid4())
    manager = FlowManager(project_id, task_id)
    
    # 验证逻辑
    errors = await manager.validate()
    if errors: raise HTTPException(status_code=400, detail={"errors": errors})

    # 创建任务记录
    await db.tasks.insert_one({
        "_id": task_id,
        "project_id": project_id,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "stats": {"total_requests": 0, "total_items": 0, "errors": 0, "current_page": 0},
        "error_message": None,
    })

    await db.projects.update_one({"_id": project_id}, {"$set": {"status": "running"}})

    # 后台异步启动分布式引擎
    async def run_and_cleanup():
        try:
            await manager.execute()
        except Exception as e:
            logger.error(f"任务 {task_id} 异步启动失败: {e}")
        finally:
            await db.projects.update_one({"_id": project_id}, {"$set": {"status": "idle"}})

    background_tasks.add_task(run_and_cleanup)
    return {"task_id": task_id, "message": "任务已分发到分布式队列"}

@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """停止任务 (分布式广播模式)"""
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    if not task: raise HTTPException(status_code=404, detail="任务不存在")

    # 1. 获取全局 MQ 连接并广播停止信号
    try:
        connection = await get_mq_connection()
        async with connection.channel() as channel:
            # 声明控制交换机
            exchange = await channel.declare_exchange("rulecrawl_controls", aio_pika.ExchangeType.FANOUT)
            # 广播停止消息
            message_body = json.dumps({"task_id": task_id, "action": "STOP"}).encode()
            await exchange.publish(aio_pika.Message(body=message_body), routing_key="")
            
        logger.info(f"已向全集群广播任务停止指令: {task_id}")
    except Exception as e:
        logger.error(f"广播停止指令失败: {e}")
        raise HTTPException(status_code=500, detail="MQ 控制总线通信失败")

    # 2. 更新数据库状态
    await db.tasks.update_one(
        {"_id": task_id},
        {"$set": {"status": "stopped", "finished_at": datetime.now(timezone.utc)}}
    )

    return {"message": "停止指令已广播", "task_id": task_id}

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    db = get_db()
    cursor = db.tasks.find({"project_id": project_id}).sort("started_at", -1).limit(20)
    return [doc async for doc in cursor]
