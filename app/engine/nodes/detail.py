"""
详情页节点 (DetailNode)
"""

from datetime import datetime, timezone
from typing import Optional
from app.engine.nodes.base import BaseNode, NodeResult, NodeRegistry
from app.engine.context import TaskContext
from app.models.download import DownloadResponse
from app.engine.parser import UniversalParser
from app.database import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)

@NodeRegistry.register("detail")
class DetailNode(BaseNode):
    async def execute(self, ctx: TaskContext, response: Optional[DownloadResponse] = None) -> NodeResult:
        if not response or not response.text:
            return NodeResult(success=False, error="缺少详情页内容")

        parser = UniversalParser(response.text, response.content_type)
        extracted_data = {}
        
        field_rules = self.parse_rules.get("fields", [])
        for rule in field_rules:
            name, selector, selector_type = rule.get("name"), rule.get("selector"), rule.get("selector_type", "xpath")
            if name and selector:
                value = parser.extract_all(selector, selector_type)
                if rule.get("clean_rules"):
                    value = UniversalParser.apply_clean_rules(value, rule["clean_rules"])
                
                # ── 核心逻辑：必填校验 ──
                if rule.get("required") and not value:
                    logger.warning(f"详情页必填字段 [{name}] 缺失，丢弃记录: {ctx.url}")
                    return NodeResult(success=False, error=f"必填字段 [{name}] 缺失", context=ctx)
                
                if value:
                    extracted_data[name] = value

        # 2. 数据合并
        extracted_data["detail_url"] = ctx.url
        # 移除透传中的内部标记
        clean_parent = {k: v for k, v in ctx.parent_data.items() if not k.startswith("_")}
        for k, v in clean_parent.items():
            if not extracted_data.get(k): extracted_data[k] = v

        # 3. 持久化 (去重逻辑略，保持核心)
        db = get_db()
        await db.data_store.insert_one({
            "project_id": ctx.project_id,
            "task_id": ctx.task_id,
            "node_id": self.node_id,
            "source_url": ctx.url,
            "crawl_time": datetime.now(timezone.utc),
            "data": extracted_data,
        })

        return NodeResult(success=True)
