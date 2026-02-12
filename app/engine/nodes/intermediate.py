"""
中间页节点（IntermediatePage）
处理重定向、获取中间 Token、过桥页面
"""

from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.context import CrawlContext
from app.engine.parser import UniversalParser
from app.utils.http_client import fetch


class IntermediateNode(BaseNode):
    """
    中间页节点

    职责：
    1. 发起 HTTP 请求（可能是为了获取 Token 或处理重定向）
    2. 可选的解析规则提取中间数据
    3. 将加工后的上下文传递给回调节点
    """

    async def execute(self, context: CrawlContext) -> NodeResult:
        url = self.request_config.get("url", "") or context.url
        if not url:
            # 如果没有配置 URL，直接传递上下文
            return NodeResult(
                success=True,
                callback_node_id=self.callback_node_id,
                context=context,
            )

        method = self.request_config.get("method", "GET")
        headers = self._merge_headers(context)
        cookies = self._merge_cookies(context)
        body = self.request_config.get("body")

        try:
            response = await fetch(
                url=url, method=method,
                headers=headers, cookies=cookies, body=body,
            )

            resp_content_type = response.headers.get("content-type", "")
            ct = "json" if "json" in resp_content_type else "html"

            new_context = context.clone(
                url=url,
                html=response.text,
                response_headers=dict(response.headers),
                headers=headers,
                cookies=cookies,
                content_type=ct,
            )

            # 如果配置了解析规则，提取中间数据存入 parent_data
            if self.parse_rules.get("fields"):
                parser = UniversalParser(response.text, ct)
                parent_data = dict(context.parent_data)
                for field_rule in self.parse_rules["fields"]:
                    value = parser.extract_first(
                        field_rule["selector"],
                        field_rule.get("selector_type", "xpath"),
                    )
                    if value:
                        parent_data[field_rule["name"]] = value
                new_context = new_context.clone(parent_data=parent_data)

            return NodeResult(
                success=True,
                callback_node_id=self.callback_node_id,
                context=new_context,
            )

        except Exception as e:
            return NodeResult(success=False, error=f"中间页请求失败: {str(e)}")
