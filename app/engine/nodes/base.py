"""
节点基类 - 职责分离版
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from app.engine.context import TaskContext
from app.models.download import DownloadResponse
from app.core.downloader import DownloaderFactory, BaseDownloader

class NodeRegistry:
    _registry = {}
    @classmethod
    def register(cls, node_type: str):
        def decorator(node_cls):
            cls._registry[node_type] = node_cls
            return node_cls
        return decorator
    @classmethod
    def get_node_class(cls, node_type: str):
        return cls._registry.get(node_type)

@dataclass
class NodeResult:
    success: bool = True
    follow_up_tasks: List[Tuple[str, TaskContext]] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    error: Optional[str] = None

class BaseNode(ABC):
    def __init__(self, node_config: dict):
        self.config = node_config
        self.node_id = node_config.get("id", "")
        self.name = node_config.get("name", "")
        self.request_config = node_config.get("request_config", {})
        self.parse_rules = node_config.get("parse_rules", {})
        self.pagination = node_config.get("pagination", {})
        self.callback_node_id = node_config.get("callback_node_id")

    async def get_downloader(self) -> BaseDownloader:
        dtype = self.request_config.get("downloader_type", "httpx")
        return await DownloaderFactory.get_downloader(dtype)

    def merge_request_args(self, ctx: TaskContext) -> dict:
        """从系统配置、节点配置和上下文(继承)合并出最终的请求参数"""
        from app.config import DEFAULT_USER_AGENT
        rc = self.request_config
        
        # 1. 合并 Headers (优先级：系统默认 < 上下文继承 < 当前节点配置)
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        headers.update(ctx.headers)
        if rc.get("headers"):
            headers.update(rc.get("headers"))
        
        # 注入动态 Referer
        if ctx.url:
            headers["Referer"] = ctx.url

        # 2. 合并 Cookies (优先级：上下文继承 < 当前节点配置)
        cookies = ctx.cookies.copy()
        if rc.get("cookies"):
            cookies.update(rc.get("cookies"))
        
        return {
            "method": rc.get("method", "GET"),
            "headers": headers,
            "cookies": cookies,
            "body": rc.get("body")
        }

    @abstractmethod
    async def execute(self, ctx: TaskContext, response: Optional[DownloadResponse] = None) -> NodeResult:
        pass
