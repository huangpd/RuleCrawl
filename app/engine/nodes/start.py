"""
起始页节点 (StartNode)
"""

import re
from typing import Optional
from app.utils.logger import get_logger
from app.engine.nodes.base import BaseNode, NodeResult, NodeRegistry
from app.engine.context import TaskContext
from app.models.download import DownloadResponse

logger = get_logger(__name__)

@NodeRegistry.register("start")
class StartNode(BaseNode):
    async def execute(self, ctx: TaskContext, response: Optional[DownloadResponse] = None) -> NodeResult:
        # 1. 提取当前节点的请求配置，用于后续透传
        config_headers = self.request_config.get("headers", {})
        config_cookies = self.request_config.get("cookies", {})
        
        # 2. 模式扩展
        raw_urls = self.request_config.get("url", [])
        all_urls = []
        for url in raw_urls:
            pattern = r"\{offset\((\d+),\s*(\d+)\)\}"
            if "{" in url and "offset" in url:
                match = re.search(pattern, url)
                if match:
                    start, end = int(match.group(1)), int(match.group(2))
                    p_str = match.group(0)
                    all_urls.extend([url.replace(p_str, str(i)) for i in range(start, end + 1)])
                    continue
            all_urls.append(url)

        # 3. 分发：将种子节点的 Headers/Cookies 注入到 Context 中，实现“权限继承”
        follow_ups = []
        target_node = self.callback_node_id or self.node_id
        
        for url in all_urls:
            follow_ups.append((target_node, ctx.clone(
                url=url, 
                headers={**ctx.headers, **config_headers},
                cookies={**ctx.cookies, **config_cookies}
            )))
        
        return NodeResult(success=True, follow_up_tasks=follow_ups)
