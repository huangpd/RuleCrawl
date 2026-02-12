"""
爬取上下文（CrawlContext）
在节点间传递的状态对象，携带 URL、响应内容、Session 信息等
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CrawlContext:
    """
    爬取上下文，在节点执行链中传递

    Attributes:
        url: 当前处理的 URL
        html: 当前页面 HTML 内容
        response_headers: 响应头
        method: 请求方法
        headers: 请求头
        cookies: Cookies
        body: POST 请求体
        content_type: 响应内容类型 (html/json/text)
        project_id: 所属项目 ID
        task_id: 所属任务 ID
        parent_data: 从父节点传递的数据
        depth: 当前递归/循环深度
        page_number: 当前页码（翻页用）
    """
    url: str = ""
    html: str = ""
    response_headers: dict = field(default_factory=dict)
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    body: Optional[str] = None
    content_type: str = "html"
    project_id: str = ""
    task_id: str = ""
    parent_data: dict = field(default_factory=dict)
    depth: int = 0
    page_number: int = 1
    source_url: str = ""  # 原始来源 URL (当 url 为 data:// 时使用)

    def clone(self, **overrides) -> "CrawlContext":
        """克隆上下文并覆盖部分字段"""
        import dataclasses
        current = dataclasses.asdict(self)
        current.update(overrides)
        return CrawlContext(**current)
