"""
采集数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DataRecord(BaseModel):
    """采集数据记录"""
    id: str = Field(..., alias="_id")
    project_id: str
    task_id: str
    source_url: str
    crawl_time: datetime
    data: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
