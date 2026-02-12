"""
任务运行记录模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TaskStats(BaseModel):
    """任务统计"""
    total_requests: int = 0
    total_items: int = 0
    errors: int = 0
    current_page: int = 0


class TaskResponse(BaseModel):
    """任务响应模型"""
    id: str = Field(..., alias="_id")
    project_id: str
    status: str = "pending"  # pending / running / completed / failed / stopped
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats: TaskStats = Field(default_factory=TaskStats)
    error_message: Optional[str] = None

    model_config = {"populate_by_name": True}
