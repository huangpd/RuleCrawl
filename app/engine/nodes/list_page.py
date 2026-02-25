"""
列表页节点（ListPage）
核心功能：解析列表并"分裂"出多个子链接任务
支持从列表项中提取非链接字段（如作者），通过 url_data 透传给详情页
"""

from urllib.parse import urljoin
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch
import logging

logger = logging.getLogger(__name__)


class ListPageNode(BaseNode):
    """
    列表页节点

    职责：
    1. 如果 HTML 为空，主动发起请求（支持配置 method/body）
    2. 解析列表并"分裂"出多个子链接任务
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        html = context.html
        content_type = context.content_type

        # ── 1. 核心修复：补回自动抓取逻辑 ──
        if not html and context.url:
            try:
                logger.info("列表页正在补全抓取 URL: %s", context.url)
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
                logger.error("列表页抓取子链接失败: %s", e)
                return NodeResult(success=False, error=f"列表页抓取失败: {str(e)}")

        if not html:
            return NodeResult(success=False, error="列表页没有收到 HTML 内容")

        parser = UniversalParser(html, content_type)
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
                        item = item_parser._json_data
                        if isinstance(item, dict):
                            item["_source_url"] = context.url  # 记录来源
                        node_items.append(item)

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

        # ── 提取下一页链接 (集成到列表页) ──
        next_url = None
        if self.pagination and self.pagination.get("selector"):
            max_pages = self.pagination.get("max_pages", 10)
            if context.page_number < max_pages:
                pg_selector = self.pagination["selector"]
                pg_type = self.pagination.get("selector_type", "xpath")
                pg_links = parser.extract(pg_selector, pg_type)
                if pg_links:
                    next_url = urljoin(context.url, pg_links[0])
                    logger.info("列表页解析到自动翻页 URL: %s", next_url)

        return NodeResult(
            success=True,
            urls=urls,
            url_data=url_data,
            items=node_items,
            next_url=next_url,  # 注入 next_url
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
            # ── 应用清洗规则 ──
            clean_rules = field_rule.get("clean_rules", [])
            if clean_rules:
                value = UniversalParser.apply_clean_rules(value, clean_rules)

            if value:
                extra[field_rule["name"]] = value
        return extra
