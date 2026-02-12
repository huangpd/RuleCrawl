"""
节点数据模型
5 种节点类型：start / intermediate / list / next / detail
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class FieldRule(BaseModel):
    """字段提取规则"""
    name: str = Field(..., description="字段名称")
    selector: str = Field(..., description="选择器表达式")
    selector_type: Literal["xpath", "css", "jsonpath", "regex"] = Field(
        "xpath", description="选择器类型"
    )
    is_link: bool = Field(False, description="是否为链接（用于列表页提取）")
    attr: Optional[str] = Field(None, description="提取属性（如 href, src）")


class RequestConfig(BaseModel):
    """HTTP 请求配置"""
    url: Optional[str] = Field("", description="请求 URL（起始页必填）")
    method: Literal["GET", "POST"] = Field("GET", description="请求方法")
    headers: Optional[dict] = Field(default_factory=dict, description="自定义请求头")
    cookies: Optional[dict] = Field(default_factory=dict, description="自定义 Cookies")
    body: Optional[str] = Field(None, description="POST 请求体")
    content_type: Optional[str] = Field(None, description="Content-Type")


class ParseRules(BaseModel):
    """解析规则配置"""
    parser_type: Literal["xpath", "css", "jsonpath", "regex"] = Field(
        "xpath", description="解析器类型"
    )
    item_selector: Optional[str] = Field(None, description="列表项选择器（列表页用）")
    item_selector_type: Optional[Literal["xpath", "css", "jsonpath", "regex"]] = Field(
        None, description="列表项选择器类型"
    )
    link_selector: Optional[str] = Field(None, description="链接选择器（列表页用）")
    link_selector_type: Optional[Literal["xpath", "css", "jsonpath", "regex"]] = Field(
        None, description="链接选择器类型"
    )
    fields: list[FieldRule] = Field(default_factory=list, description="字段提取规则列表")
    deduplication_type: Literal["none", "url", "field"] = Field(
        "none", description="去重策略：none(不去重), url(按source_url), field(按特定字段)"
    )
    deduplication_field: Optional[str] = Field(None, description="去重字段名（当类型为Field时必填）")


class PaginationConfig(BaseModel):
    """翻页配置"""
    selector: Optional[str] = Field(None, description="下一页链接选择器")
    selector_type: Literal["xpath", "css", "jsonpath", "regex"] = Field(
        "xpath", description="选择器类型"
    )
    max_pages: int = Field(10, description="最大翻页数")


class NodeCreate(BaseModel):
    """创建节点的请求体"""
    node_type: Literal["start", "intermediate", "list", "next", "detail"] = Field(
        ..., description="节点类型"
    )
    name: str = Field(..., min_length=1, max_length=200, description="节点名称")
    request_config: RequestConfig = Field(
        default_factory=RequestConfig, description="HTTP 请求配置"
    )
    parse_rules: ParseRules = Field(
        default_factory=ParseRules, description="解析规则"
    )
    pagination: Optional[PaginationConfig] = Field(
        None, description="翻页配置（下一页节点用）"
    )
    callback_node_id: Optional[str] = Field(
        None, description="回调目标节点 ID"
    )


class NodeUpdate(BaseModel):
    """更新节点的请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    request_config: Optional[RequestConfig] = None
    parse_rules: Optional[ParseRules] = None
    pagination: Optional[PaginationConfig] = None
    callback_node_id: Optional[str] = None


class NodeResponse(BaseModel):
    """节点响应模型"""
    id: str = Field(..., alias="_id")
    project_id: str
    node_type: str
    name: str
    request_config: RequestConfig
    parse_rules: ParseRules
    pagination: Optional[PaginationConfig] = None
    callback_node_id: Optional[str] = None
    created_at: datetime

    model_config = {"populate_by_name": True}
