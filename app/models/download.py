"""
RuleCrawl 下载领域模型
定义下载请求与响应的标准数据结构
"""

from typing import Optional, Dict
from pydantic import BaseModel, Field

class DownloadResponse(BaseModel):
    """
    统一的下载响应契约
    """
    url: str = Field(..., description="最终请求 URL (含重定向)")
    status_code: int = Field(..., description="HTTP 状态码")
    text: str = Field("", description="响应文本内容")
    content: bytes = Field(b"", description="原始二进制内容")
    headers: Dict[str, str] = Field(default_factory=dict, description="响应头")
    cookies: Dict[str, str] = Field(default_factory=dict, description="服务端返回的 Cookies")
    content_type: str = Field("html", description="识别出的内容类型 (html/json/xml/text)")
    elapsed: float = Field(0.0, description="请求总耗时 (秒)")
    success: bool = Field(True, description="业务判定是否成功")
    error: Optional[str] = Field(None, description="错误描述")

    model_config = {"arbitrary_types_allowed": True}
