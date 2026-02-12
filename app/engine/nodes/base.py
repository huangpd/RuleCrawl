"""
节点基类
所有标签页节点的抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from app.engine.context import CrawlContext


@dataclass
class NodeResult:
    """
    节点执行结果

    Attributes:
        success: 是否成功
        urls: 提取出的链接列表（ListPage 用）
        data: 提取出的结构化数据（DetailPage 用）
        next_url: 下一页 URL（NextPage 用）
        callback_node_id: 下一步流转到的节点 ID
        context: 更新后的上下文
        error: 错误信息
    """
    success: bool = True
    urls: list[str] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    next_url: Optional[str] = None
    callback_node_id: Optional[str] = None
    context: Optional[CrawlContext] = None
    error: Optional[str] = None


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

    @abstractmethod
    async def execute(self, context: CrawlContext) -> NodeResult:
        """
        执行节点逻辑

        Args:
            context: 爬取上下文

        Returns:
            NodeResult 执行结果
        """
        ...

    def _merge_headers(self, context: CrawlContext) -> dict:
        """合并节点配置的 Headers 和上下文中的 Headers"""
        headers = dict(context.headers)
        node_headers = self.request_config.get("headers", {})
        if node_headers:
            headers.update(node_headers)
        return headers

    def _merge_cookies(self, context: CrawlContext) -> dict:
        """合并节点配置的 Cookies 和上下文中的 Cookies"""
        cookies = dict(context.cookies)
        node_cookies = self.request_config.get("cookies", {})
        if node_cookies:
            cookies.update(node_cookies)
        return cookies
