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
    search_field: str = Query(None, description="搜索字段名"),
    keyword: str = Query(None, description="搜索关键词"),
):
    """分页查询采集数据"""
    db = get_db()

    # 验证项目存在
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 构建查询条件
    query = {"project_id": project_id}
    if search_field and keyword:
        # 支持在 data.xxx 字段下进行不区分大小写的正则模糊搜索
        query[f"data.{search_field}"] = {"$regex": keyword, "$options": "i"}

    # 总数 (带过滤)
    total = await db.data_store.count_documents(query)

    # 分页查询
    skip = (page - 1) * page_size
    cursor = (
        db.data_store
        .find(query)
        .sort("crawl_time", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        item = {
            "id": str(doc["_id"]),  # 返回内部 ID 用于后续删除操作
            "source_url": doc.get("source_url"),
            "crawl_time": doc.get("crawl_time") or doc.get("crawled_at"),
            "data": doc.get("data"),
        }
        items.append(item)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.delete("/data/{data_id}")
async def delete_single_data(data_id: str):
    """删除单条采集数据"""
    from bson import ObjectId
    db = get_db()
    try:
        result = await db.data_store.delete_one({"_id": ObjectId(data_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="数据不存在")
        return {"message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 ID 格式: {str(e)}")


@router.delete("/projects/{project_id}/data")
async def clear_data(project_id: str):
    """清空采集数据"""
    db = get_db()
    result = await db.data_store.delete_many({"project_id": project_id})
    return {"message": f"已删除 {result.deleted_count} 条数据"}
