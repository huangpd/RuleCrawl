"""
下一页节点（NextPage）
负责提取翻页 URL，实现"递归"或"循环"回目标节点
"""

from urllib.parse import urljoin
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser


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
        if not html:
            return NodeResult(success=False, error="下一页节点没有收到 HTML 内容")

        pagination = self.pagination or {}
        selector = pagination.get("selector", "")
        selector_type = pagination.get("selector_type", "xpath")
        max_pages = pagination.get("max_pages", 10)

        if not selector:
            # 没有翻页选择器，结束翻页
            return NodeResult(success=True, next_url=None, context=context)

        # 检查页数限制
        if context.page_number >= max_pages:
            return NodeResult(success=True, next_url=None, context=context)

        parser = UniversalParser(html, context.content_type)
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
