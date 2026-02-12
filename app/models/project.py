"""
项目数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    """创建项目的请求体"""
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field("", description="项目描述")


class ProjectUpdate(BaseModel):
    """更新项目的请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    """项目响应模型"""
    id: str = Field(..., alias="_id")
    name: str
    description: str = ""
    status: str = "idle"
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}
