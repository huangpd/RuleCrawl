"""
节点管理 API
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.models.node import NodeCreate, NodeUpdate

router = APIRouter(prefix="/api/v1", tags=["节点管理"])


@router.post("/projects/{project_id}/nodes")
async def create_node(project_id: str, node: NodeCreate):
    """创建节点"""
    db = get_db()

    # 验证项目存在
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    doc = {
        "_id": str(uuid.uuid4()),
        "project_id": project_id,
        "node_type": node.node_type,
        "name": node.name,
        "request_config": node.request_config.model_dump(),
        "parse_rules": node.parse_rules.model_dump(),
        "pagination": node.pagination.model_dump() if node.pagination else None,
        "callback_node_id": node.callback_node_id,
        "created_at": datetime.now(timezone.utc),
    }

    await db.nodes.insert_one(doc)
    return doc


@router.get("/projects/{project_id}/nodes")
async def list_nodes(project_id: str):
    """获取项目的所有节点"""
    db = get_db()
    nodes = []
    cursor = db.nodes.find({"project_id": project_id}).sort("created_at", 1)
    async for doc in cursor:
        nodes.append(doc)
    return nodes


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    """获取单个节点"""
    db = get_db()
    doc = await db.nodes.find_one({"_id": node_id})
    if not doc:
        raise HTTPException(status_code=404, detail="节点不存在")
    return doc


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, node: NodeUpdate):
    """更新节点"""
    db = get_db()
    existing = await db.nodes.find_one({"_id": node_id})
    if not existing:
        raise HTTPException(status_code=404, detail="节点不存在")

    update_data = {}
    if node.name is not None:
        update_data["name"] = node.name
    if node.request_config is not None:
        update_data["request_config"] = node.request_config.model_dump()
    if node.parse_rules is not None:
        update_data["parse_rules"] = node.parse_rules.model_dump()
    if node.pagination is not None:
        update_data["pagination"] = node.pagination.model_dump()
    if node.callback_node_id is not None:
        update_data["callback_node_id"] = node.callback_node_id

    if update_data:
        await db.nodes.update_one({"_id": node_id}, {"$set": update_data})

    return await db.nodes.find_one({"_id": node_id})


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str):
    """删除节点（自动清理 callback 引用）"""
    db = get_db()
    node = await db.nodes.find_one({"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 清除所有父节点对该节点的 callback 引用
    await db.nodes.update_many(
        {"callback_node_id": node_id},
        {"$set": {"callback_node_id": None}},
    )

    await db.nodes.delete_one({"_id": node_id})
    return {"message": "节点已删除", "node_id": node_id}


@router.post("/nodes/{node_id}/set-callback")
async def set_callback(node_id: str, target_node_id: str = None):
    """设置节点的回调目标"""
    db = get_db()
    node = await db.nodes.find_one({"_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="源节点不存在")

    if target_node_id:
        target = await db.nodes.find_one({"_id": target_node_id})
        if not target:
            raise HTTPException(status_code=404, detail="目标节点不存在")

    await db.nodes.update_one(
        {"_id": node_id},
        {"$set": {"callback_node_id": target_node_id}},
    )

    return {"message": "回调已设置", "node_id": node_id, "callback_node_id": target_node_id}
