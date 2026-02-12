"""
列表页节点（ListPage）
核心功能：解析列表并"分裂"出多个子链接任务
"""

from urllib.parse import urljoin
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser


class ListPageNode(BaseNode):
    """
    列表页节点

    职责：
    1. 使用 item_selector 定位列表中的每个条目
    2. 使用 link_selector 从每个条目中提取链接
    3. 将所有链接列表返回，等待 FlowManager 分发给回调节点
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        html = context.html
        if not html:
            return NodeResult(success=False, error="列表页没有收到 HTML 内容")

        parser = UniversalParser(html, context.content_type)
        parser_type = self.parse_rules.get("parser_type", "xpath")

        item_selector = self.parse_rules.get("item_selector", "")
        link_selector = self.parse_rules.get("link_selector", "")
        link_selector_type = self.parse_rules.get("link_selector_type", parser_type)

        urls = []

        if item_selector:
            # 模式 1：先选中列表项容器
            item_selector_type = self.parse_rules.get("item_selector_type", parser_type)
            items = parser.extract_items(item_selector, item_selector_type)
            
            node_items = []
            
            for item_parser in items:
                # 尝试提取链接
                links = []
                if link_selector:
                    links = item_parser.extract(link_selector, link_selector_type)
                    for link in links:
                        full_url = urljoin(context.url, link)
                        if full_url not in urls:
                            urls.append(full_url)
                else:
                    # 如果没有配置 link_selector，且是 JSON 模式，则视为数据透传
                    if item_selector_type == "jsonpath" and item_parser._json_data:
                         node_items.append(item_parser._json_data)
        
        elif link_selector:
            # 模式 2：直接用 link_selector 提取所有链接
            links = parser.extract(link_selector, link_selector_type)
            for link in links:
                full_url = urljoin(context.url, link)
                if full_url not in urls:
                    urls.append(full_url)
        
        # 同时处理 fields 中 is_link=True 的字段 (JSON 模式通常不需要这个，除非混合)
        for field_rule in self.parse_rules.get("fields", []):
            if field_rule.get("is_link"):
                links = parser.extract(
                    field_rule["selector"],
                    field_rule.get("selector_type", parser_type),
                )
                for link in links:
                    full_url = urljoin(context.url, link)
                    if full_url not in urls:
                        urls.append(full_url)

        return NodeResult(
            success=True,
            urls=urls,
            items=node_items if 'node_items' in locals() else [],
            callback_node_id=self.callback_node_id,
            context=context,
        )

        return NodeResult(
            success=True,
            urls=urls,
            callback_node_id=self.callback_node_id,
            context=context,
        )
