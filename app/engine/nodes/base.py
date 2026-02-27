"""
节点基类
所有标签页节点的抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from app.engine.context import CrawlContext
from app.core.downloader import DownloaderFactory, BaseDownloader


class NodeRegistry:
    """节点类型注册表 (单例)"""
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
    """
    节点执行结果 (Orchestrator 通讯契约)
    """
    success: bool = True
    # 核心：由节点预先拼装好的后续任务，编排器直接入队即可
    follow_up_tasks: list[tuple[str, CrawlContext]] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    context: Optional[CrawlContext] = None


class BaseNode(ABC):
    """
    节点基类 — 所有 5 种标签页的抽象

    每个节点接收一个 CrawlContext，执行自身逻辑后
    返回 NodeResult（包含下一步指令）
    """

    def __init__(self, node_config: dict):
        """
        Args:
            node_config: 从 MongoDB 加载的节点配置字典
        """
        self.config = node_config
        self.node_id = node_config.get("_id", "")
        self.node_type = node_config.get("node_type", "")
        self.name = node_config.get("name", "")
        self.request_config = node_config.get("request_config", {})
        self.parse_rules = node_config.get("parse_rules", {})
        self.pagination = node_config.get("pagination", {})
        self.callback_node_id = node_config.get("callback_node_id")

    def merge_headers(self, context_headers: dict) -> dict:
        """合并上下文 Headers 和节点配置 Headers (节点配置优先)"""
        headers = (context_headers or {}).copy()
        if self.request_config.get("headers"):
            headers.update(self.request_config.get("headers"))
        return headers

    def merge_cookies(self, context_cookies: dict) -> dict:
        """合并上下文 Cookies 和节点配置 Cookies (节点配置优先)"""
        cookies = (context_cookies or {}).copy()
        if self.request_config.get("cookies"):
            cookies.update(self.request_config.get("cookies"))
        return cookies

    async def get_downloader(self) -> BaseDownloader:
        """获取当前节点指定的下载器实例"""
        # 默认使用 httpx，用户可以在配置中指定 downloader_type
        dtype = self.request_config.get("downloader_type", "httpx")
        return await DownloaderFactory.get_downloader(dtype)

    @abstractmethod
    async def execute(self, context: CrawlContext) -> NodeResult:
        """
        执行节点逻辑

        Args:
            context: 爬取上下文

        Returns:
            NodeResult 执行结果
        """
        pass
