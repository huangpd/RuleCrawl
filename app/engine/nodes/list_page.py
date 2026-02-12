"""
列表页节点（ListPage）
核心功能：解析列表并"分裂"出多个子链接任务
支持从列表项中提取非链接字段（如作者），通过 url_data 透传给详情页
"""

from urllib.parse import urljoin
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
import logging

logger = logging.getLogger(__name__)


class ListPageNode(BaseNode):
    """
    列表页节点

    职责：
    1. 使用 item_selector 定位列表中的每个条目
    2. 使用 link_selector 从每个条目中提取链接
    3. 提取非链接字段（如作者、时间），绑定到对应 URL 的 url_data 中
    4. 将所有链接列表返回，等待 FlowManager 分发给回调节点
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
        url_data = {}   # URL → {field_name: value, ...}
        node_items = []

        if item_selector:
            # 模式 1：先选中列表项容器
            item_selector_type = self.parse_rules.get("item_selector_type", parser_type)
            items = parser.extract_items(item_selector, item_selector_type)

            for item_parser in items:
                # ── 提取链接 ──
                if link_selector:
                    links = item_parser.extract(link_selector, link_selector_type)
                    for link in links:
                        full_url = urljoin(context.url, link)
                        if full_url not in urls:
                            urls.append(full_url)

                            # ── 提取非链接字段（如作者、日期等），绑定到该 URL ──
                            extra_fields = self._extract_non_link_fields(item_parser, parser_type)
                            if extra_fields:
                                url_data[full_url] = extra_fields
                                logger.info("列表页透传数据提取成功: URL=%s, Data=%s", full_url, extra_fields)
                else:
                    # 如果没有配置 link_selector，且是 JSON 模式，则视为数据透传
                    if item_selector_type == "jsonpath" and item_parser._json_data:
                        node_items.append(item_parser._json_data)

        elif link_selector:
            # 模式 2：直接用 link_selector 提取所有链接（无 item 容器，无法提取附加字段）
            links = parser.extract(link_selector, link_selector_type)
            for link in links:
                full_url = urljoin(context.url, link)
                if full_url not in urls:
                    urls.append(full_url)

        # 同时处理 fields 中 is_link=True 的字段
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
            url_data=url_data,
            items=node_items,
            callback_node_id=self.callback_node_id,
            context=context,
        )

    def _extract_non_link_fields(self, item_parser: UniversalParser, default_type: str) -> dict:
        """
        从单个列表项中提取非链接字段（如作者、日期等）

        这些字段会通过 FlowManager → parent_data 传递到详情页，
        最终与详情页提取的数据合并后入库。

        Args:
            item_parser: 当前列表项的解析器实例
            default_type: 默认选择器类型

        Returns:
            提取到的字段字典，如 {"author": "张三", "category": "科技"}
        """
        extra = {}
        for field_rule in self.parse_rules.get("fields", []):
            if field_rule.get("is_link"):
                continue  # 跳过链接字段
            value = item_parser.extract_first(
                field_rule["selector"],
                field_rule.get("selector_type", default_type),
            )
            if value:
                extra[field_rule["name"]] = value
        return extra
