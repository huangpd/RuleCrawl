import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch
from app.database import get_db

logger = logging.getLogger(__name__)


class DetailNode(BaseNode):
    async def execute(self, context: CrawlContext) -> NodeResult:
        logger.info(f"Executing DetailNode for {context.url}")
        
        # 1. 请求页面
        content_type = "html"
        if context.url.startswith("data://"):
            html = context.html
            content_type = "json"
            logger.info("处理 data:// 协议，跳过网络请求: %s", context.url)
        else:
            try:
                response = await fetch(
                    context.url,
                    method=self.request_config.get("method", "GET"),
                    headers=self.merge_headers(context.headers),
                    cookies=self.merge_cookies(context.cookies),
                    body=self.request_config.get("body")
                )
                html = response.text
            except Exception as e:
                logger.error("详情页请求失败: URL=%s, Error=%s", context.url, e)
                return NodeResult(success=False, error=f"网络请求失败: {str(e)}", context=context)

        # 2. 解析数据
        try:
            parser = UniversalParser(html, content_type=content_type)
            extracted_data = {}
        except Exception as e:
            logger.error("解析器初始化失败: URL=%s, Error=%s", context.url, e)
            return NodeResult(success=False, error=f"解析初始化失败: {str(e)}", context=context)
        
        field_rules = self.parse_rules.get("fields", [])
        for rule in field_rules:
            name = rule.get("name")
            selector = rule.get("selector")
            selector_type = rule.get("selector_type", "xpath")
            if name and selector:
                value = parser.extract_all(selector, selector_type)
                # ── 应用清洗规则 ──
                clean_rules = rule.get("clean_rules", [])
                if clean_rules:
                    value = UniversalParser.apply_clean_rules(value, clean_rules)
                
                if value:
                    extracted_data[name] = value

        # ── 自动注入元数据字段 ──
        extracted_data["detail_url"] = context.url

        # 合并父节点传递的数据
        if context.parent_data:
            for k, v in context.parent_data.items():
                if k not in extracted_data or not extracted_data[k]:
                    extracted_data[k] = v

        # 持久化到 MongoDB (含去重逻辑)
        db = get_db()
        if db is None:
            return NodeResult(success=False, error="数据库未连接", context=context)

        should_save = True
        dedup_type = self.parse_rules.get("deduplication_type", "none")
        
        if dedup_type != "none":
            query = {"project_id": context.project_id}
            if dedup_type == "url":
                query["source_url"] = context.url
            elif dedup_type == "field":
                field = self.parse_rules.get("deduplication_field")
                if field and field in extracted_data:
                    query[f"data.{field}"] = extracted_data[field]
            
            if len(query) > 1:
                existing = await db.data_store.find_one(query)
                if existing:
                    should_save = False
                    logger.info(f"Duplicate found for {context.url}")

        if should_save:
            record = {
                "project_id": context.project_id,
                "task_id": context.task_id,
                "node_id": self.config.get("_id"),
                "source_url": context.url,
                "crawl_time": datetime.now(timezone.utc),
                "data": extracted_data,
            }
            await db.data_store.insert_one(record)
            logger.info("详情页数据入库: URL=%s, Keys=%s", context.url, list(extracted_data.keys()))

        return NodeResult(
            success=True,
            data=extracted_data,
            context=context
        )
