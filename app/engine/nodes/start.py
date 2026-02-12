"""
起始页节点（StartNode）
系统入口，初始化 Session 并发起首次请求
"""

from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.utils.http_client import fetch


class StartNode(BaseNode):
    """
    起始页节点

    职责：
    1. 从配置中获取起始 URL
    2. 注入用户配置的 Headers / Cookies
    3. 发起首次 HTTP 请求
    4. 将响应传递给回调节点
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        url = self.request_config.get("url", "") or context.url
        if not url:
            return NodeResult(success=False, error="起始页未配置 URL")

        method = self.request_config.get("method", "GET")
        headers = self._merge_headers(context)
        cookies = self._merge_cookies(context)
        body = self.request_config.get("body")
        content_type = self.request_config.get("content_type")

        try:
            response = await fetch(
                url=url,
                method=method,
                headers=headers,
                cookies=cookies,
                body=body,
                content_type=content_type,
            )

            # 判断响应内容类型
            resp_content_type = response.headers.get("content-type", "")
            if "json" in resp_content_type:
                ct = "json"
            else:
                ct = "html"

            # 更新上下文
            new_context = context.clone(
                url=url,
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
