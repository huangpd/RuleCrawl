"""
起始页节点（StartNode）
系统入口，初始化 Session 并发起首次请求
"""

import re
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.utils.http_client import fetch


class StartNode(BaseNode):
    """
    起始页节点

    职责：
    1. 支持模式解析（如 {offset(1,100)}）生成 URL 序列
    2. 支持单 URL 或 模式生成的 URL 列表分发
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        raw_input = self.request_config.get("url", "") or context.url
        if not raw_input:
            return NodeResult(success=False, error="起始页未配置 URL")

        # ── 1. 按换行符拆分多行 URL ──
        lines = [line.strip() for line in raw_input.split("\n") if line.strip()]
        all_urls = []

        for line in lines:
            # ── 2. 模式解析 logic: {offset(1, 100)} ──
            pattern_match = re.search(r"\{offset\((\d+),\s*(\d+)\)\}", line)
            if pattern_match:
                start = int(pattern_match.group(1))
                end = int(pattern_match.group(2))
                pattern_str = pattern_match.group(0)
                
                for i in range(start, end + 1):
                    all_urls.append(line.replace(pattern_str, str(i)))
            else:
                all_urls.append(line)

        # ── 3. 如果生成了多条 URL，并行分发 ──
        if len(all_urls) > 1:
            return NodeResult(
                success=True,
                urls=all_urls,
                callback_node_id=self.callback_node_id,
                context=context
            )

        # ── 4. 原有单 URL 请求逻辑 ──
        final_url = all_urls[0] if all_urls else raw_input
        method = self.request_config.get("method", "GET")
        headers = self.merge_headers(context.headers)
        cookies = self.merge_cookies(context.cookies)
        body = self.request_config.get("body")
        content_type = self.request_config.get("content_type")

        try:
            response = await fetch(
                url=final_url,
                method=method,
                headers=headers,
                cookies=cookies,
                body=body,
                content_type=content_type,
            )

            # 判断响应内容类型
            resp_content_type = response.headers.get("content-type", "")
            ct = "json" if "json" in resp_content_type else "html"

            new_context = context.clone(
                url=final_url,
                html=response.text,
                response_headers=dict(response.headers),
                headers=headers,
                cookies=cookies,
                content_type=ct,
            )

            return NodeResult(
                success=True,
                callback_node_id=self.callback_node_id,
                context=new_context,
            )

        except Exception as e:
            return NodeResult(success=False, error=f"起始页请求失败: {str(e)}")
