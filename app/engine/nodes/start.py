"""
起始页节点（StartNode）
系统入口，支持通配符模式与多 URL 分发
"""

import re
import logging
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext

logger = logging.getLogger(__name__)

class StartNode(BaseNode):
    async def execute(self, context: CrawlContext) -> NodeResult:
        # Pydantic 强类型保证了 url 字段是一个 list[str]
        raw_urls = self.request_config.get("url") or []
        if not raw_urls and context.url:
            raw_urls = [context.url]
            
        if not raw_urls:
            return NodeResult(success=False, error="起始页未配置 URL")

        # 1. 通配符扩展
        all_urls = []
        for url in raw_urls:
            match = re.search(r"\{offset\((\d+),\s*(\d+)\)\}", url)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                pattern = match.group(0)
                all_urls.extend([url.replace(pattern, str(i)) for i in range(start, end + 1)])
            else:
                all_urls.append(url)

        # 2. 多任务分发
        if len(all_urls) > 1:
            return NodeResult(success=True, urls=all_urls, callback_node_id=self.callback_node_id, context=context)

        # 3. 单请求抓取
        target_url = all_urls[0]
        try:
            downloader = await self.get_downloader()
            resp = await downloader.fetch(
                url=target_url,
                method=self.request_config.get("method", "GET"),
                headers=self.merge_headers(context.headers),
                cookies=self.merge_cookies(context.cookies),
                body=self.request_config.get("body"),
                content_type=self.request_config.get("content_type"),
            )
            return NodeResult(
                success=True,
                callback_node_id=self.callback_node_id,
                context=context.clone(url=target_url, html=resp.text, response_headers=resp.headers, content_type=resp.content_type)
            )
        except Exception as e:
            logger.error(f"StartNode 失败: {target_url}, {e}")
            return NodeResult(success=False, error=str(e))
