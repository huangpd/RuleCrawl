"""
列表页节点 (ListPage)
"""

import json
import uuid
from urllib.parse import urljoin
from typing import Optional
from app.utils.logger import get_logger
from app.engine.nodes.base import BaseNode, NodeResult, NodeRegistry
from app.engine.context import TaskContext
from app.engine.parser import UniversalParser
from app.models.download import DownloadResponse

logger = get_logger(__name__)

@NodeRegistry.register("list")
class ListPageNode(BaseNode):
    async def execute(self, ctx: TaskContext, response: Optional[DownloadResponse] = None) -> NodeResult:
        if not response or not response.text:
            return NodeResult(success=False, error="缺少页面内容")

        parser = UniversalParser(response.text, response.content_type)
        rules = self.parse_rules
        parser_type = rules.get("parser_type", "xpath")
        follow_ups = []

        # 1. 列表分裂
        item_sel = rules.get("item_selector")
        if item_sel and self.callback_node_id:
            item_type = rules.get("item_selector_type") or parser_type
            parsed_items = parser.extract_items(item_sel, item_type)

            for ip in parsed_items:
                link_sel = rules.get("link_selector")
                if link_sel:
                    # 模式 A: 提取 URL 并分发子任务
                    found_links = ip.extract(link_sel, rules.get("link_selector_type") or parser_type)
                    for l in found_links:
                        full_url = urljoin(ctx.url, l)
                        fields_data = self._extract_fields(ip, parser_type)
                        if fields_data is None: continue # 必填项缺失，丢弃
                        
                        merged_data = ctx.parent_data.copy()
                        merged_data.update(fields_data)
                        follow_ups.append((self.callback_node_id, ctx.clone(url=full_url, parent_data=merged_data)))
                else:
                    # 模式 B: 数据透传
                    fields_data = self._extract_fields(ip, parser_type)
                    if fields_data is None: continue # 必填项缺失，丢弃
                    
                    if item_type == "jsonpath" and ip._json_data:
                        fields_data.update(ip._json_data if isinstance(ip._json_data, dict) else {"_json": ip._json_data})
                    
                    virtual_ctx = ctx.clone(
                        url=f"data://{uuid.uuid4()}", 
                        source_url=ctx.url,
                        parent_data={**ctx.parent_data, **fields_data, "_virtual_html": json.dumps(fields_data, ensure_ascii=False)}
                    )
                    follow_ups.append((self.callback_node_id, virtual_ctx))

        # 2. 翻页
        pg = self.pagination
        if pg and pg.get("selector") and ctx.page_number < pg.get("max_pages", 10):
            found_next = parser.extract(pg["selector"], pg.get("selector_type", "xpath"))
            if found_next:
                next_url = urljoin(ctx.url, found_next[0])
                follow_ups.append((self.node_id, ctx.clone(url=next_url, page_number=ctx.page_number + 1)))

        return NodeResult(success=True, follow_up_tasks=follow_ups)

    def _extract_fields(self, ip: UniversalParser, default_type: str) -> Optional[dict]:
        """提取字段，处理必填逻辑"""
        extra = {}
        for f in self.parse_rules.get("fields", []):
            val = ip.extract_first(f["selector"], f.get("selector_type", default_type))
            if f.get("clean_rules"):
                val = UniversalParser.apply_clean_rules(val, f["clean_rules"])
            
            # 必填校验
            if f.get("required") and not val:
                return None
                
            if val: extra[f["name"]] = val
        return extra
