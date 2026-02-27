"""
列表页节点（ListPage）
核心功能：解析列表并产生后续采集任务
支持从列表项中提取字段透传，以及集成翻页
"""

import json
import uuid
from urllib.parse import urljoin
import logging
from app.engine.nodes.base import BaseNode, NodeResult, NodeRegistry
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser

logger = logging.getLogger(__name__)

@NodeRegistry.register("list")
class ListPageNode(BaseNode):
    async def execute(self, context: CrawlContext) -> NodeResult:
        html, content_type = context.html, context.content_type

        # 1. 抓取逻辑补全 (如果当前上下文没内容)
        if not html and context.url:
            try:
                downloader = await self.get_downloader()
                resp = await downloader.fetch(
                    context.url, 
                    method="GET", 
                    headers=self.merge_headers(context.headers), 
                    cookies=self.merge_cookies(context.cookies)
                )
                html, content_type = resp.text, resp.content_type
                context = context.clone(html=html, content_type=content_type)
            except Exception as e:
                return NodeResult(success=False, error=f"列表页请求失败: {e}")

        if not html:
            return NodeResult(success=False, error="无内容")

        # 2. 初始化解析器
        parser = UniversalParser(html, content_type)
        rules = self.parse_rules
        parser_type = rules.get("parser_type", "xpath")
        
        follow_ups = []

        # 3. 提取子任务 (裂变)
        item_sel = rules.get("item_selector")
        if item_sel and self.callback_node_id:
            item_type = rules.get("item_selector_type") or parser_type
            parsed_items = parser.extract_items(item_sel, item_type)

            for ip in parsed_items:
                link_sel = rules.get("link_selector")
                if link_sel:
                    # A. 提取 URL 任务
                    found_links = ip.extract(link_sel, rules.get("link_selector_type") or parser_type)
                    for l in found_links:
                        full_url = urljoin(context.url, l)
                        # 拼装透传数据
                        merged_data = context.parent_data.copy()
                        merged_data.update(self._extract_fields(ip, parser_type))
                        
                        follow_ups.append((
                            self.callback_node_id, 
                            context.clone(url=full_url, html="", parent_data=merged_data)
                        ))
                elif item_type == "jsonpath" and ip._json_data:
                    # B. JSON 直接透传模式 (虚拟 data:// 协议)
                    follow_ups.append((
                        self.callback_node_id,
                        context.clone(
                            url=f"data://{uuid.uuid4()}", 
                            html=json.dumps(ip._json_data, ensure_ascii=False), 
                            content_type="json",
                            source_url=context.url
                        )
                    ))

        # 4. 自动翻页 (产生指向自身的后续任务)
        pg = self.pagination
        if pg and pg.get("selector") and context.page_number < pg.get("max_pages", 10):
            found_next = parser.extract(pg["selector"], pg.get("selector_type", "xpath"))
            if found_next:
                next_url = urljoin(context.url, found_next[0])
                follow_ups.append((
                    self.config["id"], # 指向自身
                    context.clone(url=next_url, html="", page_number=context.page_number + 1)
                ))

        return NodeResult(success=True, follow_up_tasks=follow_ups, context=context)

    def _extract_fields(self, ip: UniversalParser, default_type: str) -> dict:
        extra = {}
        for f in self.parse_rules.get("fields", []):
            val = ip.extract_first(f["selector"], f.get("selector_type", default_type))
            if f.get("clean_rules"):
                val = UniversalParser.apply_clean_rules(val, f["clean_rules"])
            if val: extra[f["name"]] = val
        return extra
