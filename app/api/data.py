"""
采集数据查询 API
"""

from fastapi import APIRouter, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/api/v1", tags=["数据管理"])


@router.get("/projects/{project_id}/data")
async def list_data(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """分页查询采集数据"""
    db = get_db()

    # 验证项目存在
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 总数
    total = await db.data_store.count_documents({"project_id": project_id})

    # 分页查询
    skip = (page - 1) * page_size
    cursor = (
        db.data_store
        .find({"project_id": project_id})
        .sort("crawl_time", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        items.append(doc)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.delete("/projects/{project_id}/data")
async def clear_data(project_id: str):
    """清空采集数据"""
    db = get_db()
    result = await db.data_store.delete_many({"project_id": project_id})
    return {"message": f"已删除 {result.deleted_count} 条数据"}
