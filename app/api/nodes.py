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
    """
    删除节点及其所有后续子节点（递归级联删除）
    """
    db = get_db()
    
    # 1. 验证要删除的根节点是否存在
    root_node = await db.nodes.find_one({"_id": node_id})
    if not root_node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 2. 递归收集所有下游节点 ID
    to_delete_ids = set()
    
    async def collect_descendants(current_id):
        if not current_id or current_id in to_delete_ids:
            return
        to_delete_ids.add(current_id)
        
        # 查找以此节点为 callback 的节点（正向链路）
        node = await db.nodes.find_one({"_id": current_id})
        if node and node.get("callback_node_id"):
            await collect_descendants(node["callback_node_id"])
            
        # 查找是否有翻页节点指向此节点（逆向翻页链路，也要处理）
        # 如果当前是 ListPage，删了它，那么指向它的 NextPage 也该删
        async for next_node in db.nodes.find({"node_type": "next", "callback_node_id": current_id}):
            await collect_descendants(next_node["_id"])

    await collect_descendants(node_id)

    # 3. 清理所有父节点对这批待删节点的 callback 引用（防止悬空）
    # 只有那些不在 to_delete_ids 中的父节点需要清理
    await db.nodes.update_many(
        {"callback_node_id": {"$in": list(to_delete_ids)}},
        {"$set": {"callback_node_id": None}},
    )

    # 4. 执行批量删除
    result = await db.nodes.delete_many({"_id": {"$in": list(to_delete_ids)}})
    
    return {
        "message": f"成功删除节点及其子节点，共计 {result.deleted_count} 个",
        "deleted_ids": list(to_delete_ids)
    }


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
