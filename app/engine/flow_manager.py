"""
工作流管理器（Flow Manager）
负责编排节点执行顺序，驱动整个爬虫流程
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.engine.context import CrawlContext
from app.engine.nodes.base import BaseNode, NodeResult
from app.engine.nodes.start import StartNode
from app.engine.nodes.list_page import ListPageNode
from app.engine.nodes.detail import DetailNode
from app.utils.http_client import fetch
from app.config import MAX_CONCURRENT_REQUESTS

logger = logging.getLogger(__name__)

# 节点类型 → 节点类的映射 (已精简，移除独立翻页和中间页节点)
NODE_CLASS_MAP = {
    "start": StartNode,
    "list": ListPageNode,
    "detail": DetailNode,
}


class FlowManager:
    """
    工作流管理器

    职责：
    1. 从数据库加载项目的所有节点配置
    2. 构建节点执行图
    3. 从 StartNode 开始，按 callback 链调度执行
    4. 处理列表页"分裂"和集成翻页循环
    """

    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id
        self.nodes: dict[str, dict] = {}  # node_id → node_config
        self._stop_flag = False

    async def load_nodes(self):
        """从数据库加载项目所有节点"""
        db = get_db()
        cursor = db.nodes.find({"project_id": self.project_id})
        async for node_doc in cursor:
            self.nodes[node_doc["_id"]] = node_doc

    def get_start_node(self) -> Optional[dict]:
        """获取起始节点（类型为 start 的节点）"""
        for node in self.nodes.values():
            if node["node_type"] == "start":
                return node
        return None

    def create_node_instance(self, node_config: dict) -> BaseNode:
        """根据配置创建节点实例"""
        node_type = node_config["node_type"]
        cls = NODE_CLASS_MAP.get(node_type)
        if not cls:
            raise ValueError(f"未知的节点类型: {node_type}")
        return cls(node_config)

    def stop(self):
        """停止执行"""
        self._stop_flag = True

    async def execute(self):
        """
        执行完整的爬虫工作流
        """
        db = get_db()

        # 更新任务状态为运行中
        await db.tasks.update_one(
            {"_id": self.task_id},
            {"$set": {"status": "running", "started_at": datetime.now(timezone.utc)}},
        )

        try:
            await self.load_nodes()

            start_node_config = self.get_start_node()
            if not start_node_config:
                raise ValueError("项目没有配置起始页节点")

            # 初始化上下文
            context = CrawlContext(
                project_id=self.project_id,
                task_id=self.task_id,
            )

            # 从起始节点开始执行
            await self._execute_node(start_node_config["_id"], context)

            # 更新任务状态为完成
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$set": {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc),
                }},
            )

        except ValueError as e:
            logger.error("工作流配置错误: %s", e)
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$set": {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc),
                    "error_message": f"配置错误: {str(e)}",
                }},
            )
        except Exception as e:
            logger.error("工作流运行时异常: %s", e, exc_info=True)
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$set": {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc),
                    "error_message": f"运行时异常: {str(e)}",
                }},
            )

    async def _execute_node(self, node_id: str, context: CrawlContext):
        """递归执行节点"""
        if self._stop_flag:
            return

        node_config = self.nodes.get(node_id)
        if not node_config:
            logger.error("找不到节点配置: %s", node_id)
            return

        try:
            node = self.create_node_instance(node_config)
            result = await node.execute(context)
        except Exception as e:
            logger.error("节点 [%s] 执行发生崩溃: %s", node_config.get("name", node_id), e, exc_info=True)
            db = get_db()
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.errors": 1}},
            )
            return

        db = get_db()

        if not result.success:
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.errors": 1}},
            )
            logger.warning("节点 [%s] 业务处理失败: %s", node.name, result.error)
            return

        # 更新请求计数
        await db.tasks.update_one(
            {"_id": self.task_id},
            {"$inc": {"stats.total_requests": 1}},
        )

        updated_context = result.context or context

        # 根据节点类型处理后续逻辑
        if node_config["node_type"] == "detail":
            # 详情页是终点，数据已入库
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.total_items": 1}},
            )
            return

        if node_config["node_type"] == "list":
            # 列表页：分裂出多个子任务 + 集成翻页循环
            await self._handle_list_result(result, updated_context, node_config)
            return

        # ── 核心逻辑：支持 Start 节点的任务分裂 (如通配符 URL) ──
        if node_config["node_type"] == "start" and result.urls and result.callback_node_id:
            logger.info("起始页产生了多条 URL (%d 条)，正在并行分发...", len(result.urls))
            from app.config import MAX_CONCURRENT_REQUESTS
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

            async def dispatch(url: str):
                async with semaphore:
                    if self._stop_flag:
                        return
                    # 复制当前上下文（保留 Headers/Cookies 等），清除 HTML
                    child_context = updated_context.clone(url=url, html="")
                    await self._execute_node(result.callback_node_id, child_context)

            tasks = [dispatch(url) for url in result.urls]
            await asyncio.gather(*tasks, return_exceptions=True)
            return

        # 其他节点（如 Start 只有单条 URL）：直接流转到回调节点
        if result.callback_node_id:
            await self._execute_node(result.callback_node_id, updated_context)

    async def _handle_list_result(
        self, result: NodeResult, context: CrawlContext, list_node_config: dict
    ):
        """
        处理列表页结果：并行处理子链接 + 迭代翻页
        """
        current_result = result
        current_context = context
        db = get_db()

        while True:
            if self._stop_flag:
                return

            # 1. 并行处理当前页的子链接 / 数据项
            if (current_result.urls or current_result.items) and current_result.callback_node_id:
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

                async def process_url(url: str):
                    async with semaphore:
                        if self._stop_flag:
                            return
                        new_parent_data = current_context.parent_data.copy()
                        extra_fields = current_result.url_data.get(url, {})
                        if extra_fields:
                            new_parent_data.update(extra_fields)

                        child_context = current_context.clone(
                            url=url, html="", parent_data=new_parent_data
                        )
                        await self._execute_node(current_result.callback_node_id, child_context)

                async def process_item(item: dict):
                    async with semaphore:
                        if self._stop_flag:
                            return
                        virtual_url = f"data://{uuid.uuid4()}"
                        content = json.dumps(item, ensure_ascii=False)

                        child_context = current_context.clone(
                            url=virtual_url,
                            html=content,
                            content_type="json",
                            source_url=current_context.url
                        )
                        await self._execute_node(current_result.callback_node_id, child_context)

                tasks = []
                if current_result.urls:
                    tasks.extend([process_url(url) for url in current_result.urls])
                if current_result.items:
                    tasks.extend([process_item(item) for item in current_result.items])

                await asyncio.gather(*tasks, return_exceptions=True)

            # 2. 确定下一页 URL (仅支持集成翻页模式)
            next_url = current_result.next_url
            if not next_url:
                break 

            # 3. 获取下一页内容
            try:
                response = await fetch(
                    url=next_url,
                    headers=current_context.headers,
                    cookies=current_context.cookies,
                )
                next_context = current_context.clone(
                    url=next_url,
                    html=response.text,
                    page_number=current_context.page_number + 1,
                )
            except Exception as e:
                logger.warning("翻页请求失败: URL=%s, Error=%s", next_url, e)
                break 

            # 4. 在新页面上重新执行列表页 (保持同一节点实例逻辑)
            list_node_instance = self.create_node_instance(list_node_config)
            new_list_result = await list_node_instance.execute(next_context)

            if not new_list_result.success:
                await db.tasks.update_one(
                    {"_id": self.task_id},
                    {"$inc": {"stats.errors": 1}},
                )
                break

            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.total_requests": 1}},
            )

            # 5. 进入下一轮循环
            current_result = new_list_result
            current_context = new_list_result.context or next_context

    async def validate(self) -> list[str]:
        """验证工作流合法性"""
        errors = []
        await self.load_nodes()

        if not self.nodes:
            errors.append("项目没有配置任何节点")
            return errors

        start_node = self.get_start_node()
        if not start_node:
            errors.append("缺少起始页节点")

        for node in self.nodes.values():
            cb_id = node.get("callback_node_id")
            if cb_id and cb_id not in self.nodes:
                errors.append(f"节点 [{node['name']}] 的回调目标 {cb_id} 不存在")
            
            # 针对详情页的额外检查
            if node["node_type"] == "detail":
                rules = node.get("parse_rules", {})
                if rules.get("deduplication_type") == "field" and not rules.get("deduplication_field"):
                    errors.append(f"详情页节点 [{node['name']}] 开启了字段去重，但未指定具体字段名")

        return errors
