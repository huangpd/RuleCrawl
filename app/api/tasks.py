"""
任务运行 API
"""

import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.database import get_db
from app.engine.flow_manager import FlowManager

router = APIRouter(prefix="/api/v1", tags=["任务管理"])

# 运行中的任务管理器引用（用于停止任务）
_running_managers: dict[str, FlowManager] = {}


@router.post("/projects/{project_id}/run")
async def run_project(project_id: str, background_tasks: BackgroundTasks):
    """启动爬虫任务"""
    db = get_db()

    # 验证项目存在
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 验证工作流合法性
    task_id = str(uuid.uuid4())
    manager = FlowManager(project_id, task_id)
    errors = await manager.validate()
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # 创建任务记录
    task_doc = {
        "_id": task_id,
        "project_id": project_id,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "stats": {
            "total_requests": 0,
            "total_items": 0,
            "errors": 0,
            "current_page": 0,
        },
        "error_message": None,
    }
    await db.tasks.insert_one(task_doc)

    # 更新项目状态
    await db.projects.update_one(
        {"_id": project_id}, {"$set": {"status": "running"}}
    )

    # 后台执行爬虫
    _running_managers[task_id] = manager

    async def run_and_cleanup():
        try:
            await manager.execute()
        finally:
            _running_managers.pop(task_id, None)
            await db.projects.update_one(
                {"_id": project_id}, {"$set": {"status": "idle"}}
            )

    background_tasks.add_task(run_and_cleanup)

    return {"task_id": task_id, "message": "任务已启动"}


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """查询任务状态"""
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """停止任务"""
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    manager = _running_managers.get(task_id)
    if manager:
        manager.stop()
        _running_managers.pop(task_id, None)

    await db.tasks.update_one(
        {"_id": task_id},
        {"$set": {
            "status": "stopped",
            "finished_at": datetime.now(timezone.utc),
        }},
    )

    return {"message": "任务已停止", "task_id": task_id}


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    """获取项目的所有任务"""
    db = get_db()
    tasks = []
    cursor = db.tasks.find({"project_id": project_id}).sort("started_at", -1).limit(20)
    async for doc in cursor:
        tasks.append(doc)
    return tasks
