"""
列表页节点（ListPage）
核心功能：解析列表并"分裂"出多个子任务
支持从列表项中提取字段，通过 url_data 透传
"""

from urllib.parse import urljoin
from app.utils.logger import get_logger
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch
from app.utils.logger import get_logger
logger = get_logger(__name__)

class ListPageNode(BaseNode):
    async def execute(self, context: CrawlContext) -> NodeResult:
        html, content_type = context.html, context.content_type

        # 1. 抓取逻辑补全
        if not html and context.url:
            try:
                resp = await fetch(context.url, method="GET", headers=self.merge_headers(context.headers), cookies=self.merge_cookies(context.cookies))
                html, content_type = resp.text, ("json" if "json" in resp.headers.get("content-type", "") else "html")
                context = context.clone(html=html, content_type=content_type)
            except Exception as e:
                return NodeResult(success=False, error=f"请求失败: {e}")

        if not html:
            return NodeResult(success=False, error="无内容")

        # 2. 解析器初始化
        parser = UniversalParser(html, content_type)
        parser_type = self.parse_rules.get("parser_type", "xpath")
        urls, url_data, items = [], {}, []

        # 3. 提取逻辑
        item_sel = self.parse_rules.get("item_selector")
        if item_sel:
            item_type = self.parse_rules.get("item_selector_type") or parser_type
            parsed_items = parser.extract_items(item_sel, item_type)

            for ip in parsed_items:
                link_sel = self.parse_rules.get("link_selector")
                if link_sel:
                    # 抓取模式
                    found_links = ip.extract(link_sel, self.parse_rules.get("link_selector_type") or parser_type)
                    for l in found_links:
                        full_url = urljoin(context.url, l)
                        if full_url not in urls:
                            urls.append(full_url)
                            extra = self._extract_fields(ip, parser_type)
                            if extra: url_data[full_url] = extra
                elif item_type == "jsonpath" and ip._json_data:
                    # JSON 透传模式
                    items.append(ip._json_data)

        # 4. 自动翻页
        next_url = None
        pg = self.pagination
        if pg and pg.get("selector") and context.page_number < pg.get("max_pages", 10):
            found_next = parser.extract(pg["selector"], pg.get("selector_type", "xpath"))
            if found_next: next_url = urljoin(context.url, found_next[0])

        return NodeResult(success=True, urls=urls, url_data=url_data, items=items, next_url=next_url, callback_node_id=self.callback_node_id, context=context)

    def _extract_fields(self, ip: UniversalParser, default_type: str) -> dict:
        extra = {}
        for f in self.parse_rules.get("fields", []):
            val = ip.extract_first(f["selector"], f.get("selector_type", default_type))
            if f.get("clean_rules"):
                val = UniversalParser.apply_clean_rules(val, f["clean_rules"])
            if val: extra[f["name"]] = val
        return extra
