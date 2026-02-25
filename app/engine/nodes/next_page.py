"""
下一页节点（NextPage）
负责提取翻页 URL，实现"递归"或"循环"回目标节点
"""

from urllib.parse import urljoin
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch
import logging

logger = logging.getLogger(__name__)


class NextPageNode(BaseNode):
    """
    下一页节点

    职责：
    1. 从当前页面提取"下一页"链接
    2. 检查是否超过最大页数限制
    3. 返回下一页 URL，FlowManager 将其回调到目标节点（通常是 ListPage）
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        html = context.html
        content_type = context.content_type

        # ── 自动抓取逻辑 (兜底) ──
        if not html and context.url:
            if context.url.startswith("data://"):
                 return NodeResult(success=False, error="下一页节点无法处理 data:// 协议的自动抓取")

            try:
                logger.info("下一页节点正在兜底抓取内容: %s", context.url)
                response = await fetch(
                    url=context.url,
                    method="GET",
                    headers=self.merge_headers(context.headers),
                    cookies=self.merge_cookies(context.cookies),
                )
                html = response.text
                resp_content_type = response.headers.get("content-type", "")
                content_type = "json" if "json" in resp_content_type else "html"
                context = context.clone(html=html, content_type=content_type)
            except Exception as e:
                return NodeResult(success=False, error=f"翻页提取时抓取失败: {str(e)}")

        if not html:
            return NodeResult(success=False, error="下一页节点没有收到 HTML 内容")

        pagination = self.pagination or {}
        selector = pagination.get("selector", "")
        selector_type = pagination.get("selector_type", "xpath")
        max_pages = pagination.get("max_pages", 10)

        if not selector:
            # 没有翻页选择器，结束翻页
            return NodeResult(success=True, next_url=None, context=context)

        # 检查页数限制 (context.page_number 从 1 开始)
        if context.page_number >= max_pages:
            logger.info("达到最大翻页限制: %d", max_pages)
            return NodeResult(success=True, next_url=None, context=context)

        parser = UniversalParser(html, content_type)
        next_links = parser.extract(selector, selector_type)

        if next_links:
            next_url = urljoin(context.url, next_links[0])
            new_context = context.clone(
                page_number=context.page_number + 1,
            )
            return NodeResult(
                success=True,
                next_url=next_url,
                callback_node_id=self.callback_node_id,
                context=new_context,
            )

        # 没有找到下一页链接，翻页结束
        return NodeResult(success=True, next_url=None, context=context)
