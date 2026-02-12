"""
详情页节点（DetailPage）
核心功能：按字段规则提取数据并持久化到 MongoDB
"""

from datetime import datetime, timezone
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch
from app.database import get_db
import uuid


class DetailNode(BaseNode):
    """
    详情页节点

    职责：
    1. 请求详情页 URL
    2. 根据用户定义的字段规则提取数据
    3. 将结构化数据持久化到 MongoDB data_store 集合
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        url = context.url
        if not url:
            return NodeResult(success=False, error="详情页没有收到 URL")

        resp_content_type = ""
        html = ""

        # 检查是否为虚拟 URL (data://)
        if url.lower().startswith("data://"):
            html = context.html or ""
            resp_content_type = context.content_type or "json"
        else:
            # 发起请求获取详情页内容
            headers = self._merge_headers(context)
            cookies = self._merge_cookies(context)
            method = self.request_config.get("method", "GET")

            try:
                response = await fetch(
                    url=url, method=method,
                    headers=headers, cookies=cookies,
                )
                html = response.text
                resp_content_type = response.headers.get("content-type", "")
            except Exception as e:
                return NodeResult(success=False, error=f"详情页请求失败: {str(e)}")

        ct = "json" if "json" in resp_content_type else "html"

        parser = UniversalParser(html, ct)
        parser_type = self.parse_rules.get("parser_type", "xpath")

        # 提取字段
        extracted_data = {}
        for field_rule in self.parse_rules.get("fields", []):
            field_name = field_rule["name"]
            selector = field_rule["selector"]
            sel_type = field_rule.get("selector_type", parser_type)

            value = parser.extract_first(selector, sel_type)
            extracted_data[field_name] = value

        # 合并父节点传递的数据
        if context.parent_data:
            for k, v in context.parent_data.items():
                if k not in extracted_data or not extracted_data[k]:
                    extracted_data[k] = v

        # 持久化到 MongoDB (含去重逻辑)
        db = get_db()
        if db is not None:
            should_save = True
            dedup_type = self.parse_rules.get("deduplication_type", "none")
            
            if dedup_type != "none":
                query = {"project_id": context.project_id}
                if dedup_type == "url":
                    query["source_url"] = url
                elif dedup_type == "field":
                    field = self.parse_rules.get("deduplication_field")
                    if field and field in extracted_data and extracted_data[field]:
                         query[f"data.{field}"] = extracted_data[field]
                
                # 只有当查询条件除了 project_id 外还有其他条件时才执行查询
                if len(query) > 1:
                    existing = await db.data_store.find_one(query)
                    if existing:
                        should_save = False
                        # 可以选择记录日志或在结果中标记
            
            if should_save:
                record = {
                    "_id": str(uuid.uuid4()),
                    "project_id": context.project_id,
                    "task_id": context.task_id,
                    "source_url": url,
                    "crawl_time": datetime.now(timezone.utc),
                    "data": extracted_data,
                }
                await db.data_store.insert_one(record)

        return NodeResult(
            success=True,
            data=extracted_data,
            context=context,
        )
