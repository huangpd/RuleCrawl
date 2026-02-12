"""
项目管理 API
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.database import get_db
from app.models.project import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["项目管理"])


@router.post("")
async def create_project(project: ProjectCreate):
    """创建新项目"""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "_id": str(uuid.uuid4()),
        "name": project.name,
        "description": project.description or "",
        "status": "idle",
        "created_at": now,
        "updated_at": now,
    }
    await db.projects.insert_one(doc)
    return doc


@router.get("")
async def list_projects(
    page: int = 1,
    page_size: int = 20,
    keyword: str = None
):
    """获取所有项目（支持分页和搜索）"""
    db = get_db()
    
    query = {}
    if keyword:
        query["name"] = {"$regex": keyword, "$options": "i"}

    total = await db.projects.count_documents(query)
    
    cursor = db.projects.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = []
    async for doc in cursor:
        items.append(doc)
        
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/{project_id}")
async def get_project(project_id: str):
    """获取单个项目"""
    db = get_db()
    doc = await db.projects.find_one({"_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="项目不存在")
    return doc


@router.put("/{project_id}")
async def update_project(project_id: str, project: ProjectUpdate):
    """更新项目"""
    db = get_db()
    existing = await db.projects.find_one({"_id": project_id})
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = {}
    if project.name is not None:
        update_data["name"] = project.name
    if project.description is not None:
        update_data["description"] = project.description
    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.projects.update_one({"_id": project_id}, {"$set": update_data})
    return await db.projects.find_one({"_id": project_id})


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """删除项目（级联删除节点、任务和数据）"""
    db = get_db()
    existing = await db.projects.find_one({"_id": project_id})
    if not existing:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 级联删除
    await db.nodes.delete_many({"project_id": project_id})
    await db.tasks.delete_many({"project_id": project_id})
    await db.data_store.delete_many({"project_id": project_id})
    await db.projects.delete_one({"_id": project_id})

    return {"message": "项目已删除", "project_id": project_id}
