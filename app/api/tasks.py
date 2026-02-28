"""
任务管理 API - 分布式版 (Broker 抽象)
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.database import get_db
from app.engine.flow_manager import FlowManager
from app.core.broker import RabbitMQBroker
from app.config import RABBITMQ_URL

router = APIRouter(prefix="/api/v1", tags=["任务管理"])

@router.post("/projects/{project_id}/run")
async def run_project(project_id: str, background_tasks: BackgroundTasks):
    db = get_db()
    project = await db.projects.find_one({"_id": project_id})
    if not project: raise HTTPException(status_code=404, detail="项目不存在")

    task_id = str(uuid.uuid4())
    manager = FlowManager(project_id, task_id)
    
    await db.tasks.insert_one({
        "_id": task_id,
        "project_id": project_id,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "stats": {"total_requests": 0, "total_items": 0, "errors": 0, "current_page": 0},
    })

    async def run_and_cleanup():
        try:
            await manager.execute()
        finally:
            await db.projects.update_one({"_id": project_id}, {"$set": {"status": "idle"}})

    await db.projects.update_one({"_id": project_id}, {"$set": {"status": "running"}})
    background_tasks.add_task(run_and_cleanup)
    return {"task_id": task_id}

@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    # 利用 Broker 广播停止信号
    broker = RabbitMQBroker(RABBITMQ_URL)
    await broker.connect()
    await broker.broadcast_control(task_id, "STOP")
    await broker.close()
    
    db = get_db()
    await db.tasks.update_one(
        {"_id": task_id},
        {"$set": {"status": "stopped", "finished_at": datetime.now(timezone.utc)}}
    )
    return {"message": "停止指令已广播"}

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    return task

@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    db = get_db()
    cursor = db.tasks.find({"project_id": project_id}).sort("started_at", -1).limit(20)
    return [doc async for doc in cursor]
