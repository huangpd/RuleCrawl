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
from app.engine.nodes.intermediate import IntermediateNode
from app.engine.nodes.list_page import ListPageNode
from app.engine.nodes.next_page import NextPageNode
from app.engine.nodes.detail import DetailNode
from app.utils.http_client import fetch
from app.config import MAX_CONCURRENT_REQUESTS

logger = logging.getLogger(__name__)

# 节点类型 → 节点类的映射
NODE_CLASS_MAP = {
    "start": StartNode,
    "intermediate": IntermediateNode,
    "list": ListPageNode,
    "next": NextPageNode,
    "detail": DetailNode,
}


class FlowManager:
    """
    工作流管理器

    职责：
    1. 从数据库加载项目的所有节点配置
    2. 构建节点执行图
    3. 从 StartNode 开始，按 callback 链调度执行
    4. 处理列表页"分裂"和下一页"循环"
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

        流程：
        1. 找到 StartNode 并执行
        2. 根据 callback_node_id 链式调度后续节点
        3. 列表页产生的多个 URL 并行分发到回调节点
        4. 下一页节点产生的 URL 循环回目标节点
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

        except Exception as e:
            logger.error("工作流执行异常: %s", e, exc_info=True)
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$set": {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc),
                    "error_message": str(e),
                }},
            )

    async def _execute_node(self, node_id: str, context: CrawlContext):
        """递归执行节点"""
        if self._stop_flag:
            return

        node_config = self.nodes.get(node_id)
        if not node_config:
            return

        node = self.create_node_instance(node_config)
        result = await node.execute(context)

        db = get_db()

        if not result.success:
            # 记录错误但不中断整个流程
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.errors": 1}},
            )
            logger.warning("节点 [%s] 执行失败: %s", node.name, result.error)
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
            # 列表页：分裂出多个子任务（使用循环翻页，避免递归栈溢出）
            await self._handle_list_result(result, updated_context, node_config)
            return

        if node_config["node_type"] == "next":
            # 下一页：循环回调
            await self._handle_next_result(result, updated_context)
            return

        # 其他节点（start / intermediate）：直接流转到回调节点
        if result.callback_node_id:
            await self._execute_node(result.callback_node_id, updated_context)

    async def _handle_list_result(
        self, result: NodeResult, context: CrawlContext, list_node_config: dict
    ):
        """
        处理列表页结果：并行处理子链接 + 迭代翻页

        使用 while 循环替代递归调用，避免深度翻页时栈溢出。
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
                        # 将列表页提取的附加字段（如作者）注入到子上下文的 parent_data
                        extra_fields = current_result.url_data.get(url, {})
                        if extra_fields:
                            logger.info("FlowManager 传递透传数据: URL=%s, Data=%s", url, extra_fields)

                        child_context = current_context.clone(
                            url=url, html="", parent_data=extra_fields
                        )
                        await self._execute_node(current_result.callback_node_id, child_context)

                async def process_item(item: dict):
                    async with semaphore:
                        if self._stop_flag:
                            return
                        # 生成虚拟 URL 和 JSON 内容
                        virtual_url = f"data://{uuid.uuid4()}"
                        content = json.dumps(item, ensure_ascii=False)

                        child_context = current_context.clone(
                            url=virtual_url,
                            html=content,  # 将 JSON 数据作为页面内容
                            content_type="json",
                            source_url=current_context.url  # 记录来源
                        )
                        await self._execute_node(current_result.callback_node_id, child_context)

                tasks = []
                if current_result.urls:
                    tasks.extend([process_url(url) for url in current_result.urls])
                if current_result.items:
                    tasks.extend([process_item(item) for item in current_result.items])

                await asyncio.gather(*tasks, return_exceptions=True)

            # 2. 查找是否有 NextPage 节点进行翻页
            next_node_config = self._find_next_node_for_list(list_node_config)
            if not next_node_config:
                break  # 无翻页节点，结束循环

            next_node = self.create_node_instance(next_node_config)
            next_result = await next_node.execute(current_context)

            if not next_result.success or not next_result.next_url:
                break  # 翻页结束（无下一页或翻页失败）

            # 3. 获取下一页内容
            try:
                headers = current_context.headers
                cookies = current_context.cookies
                response = await fetch(
                    url=next_result.next_url,
                    headers=headers,
                    cookies=cookies,
                )
                next_context = (next_result.context or current_context).clone(
                    url=next_result.next_url,
                    html=response.text,
                )
            except Exception as e:
                logger.warning("翻页请求失败: %s", e)
                break  # 翻页请求异常，结束循环

            # 4. 在新的页面上重新执行 ListNode，得到新结果
            callback_id = next_node_config.get("callback_node_id") or list_node_config["_id"]
            callback_config = self.nodes.get(callback_id)
            if not callback_config:
                break

            list_node_instance = self.create_node_instance(callback_config)
            new_list_result = await list_node_instance.execute(next_context)

            if not new_list_result.success:
                await db.tasks.update_one(
                    {"_id": self.task_id},
                    {"$inc": {"stats.errors": 1}},
                )
                logger.warning("翻页后列表页执行失败: %s", new_list_result.error)
                break

            # 更新请求计数
            await db.tasks.update_one(
                {"_id": self.task_id},
                {"$inc": {"stats.total_requests": 1}},
            )

            # 5. 以新结果进入下一轮循环
            current_result = new_list_result
            current_context = new_list_result.context or next_context

    def _find_next_node_for_list(self, list_node_config: dict) -> Optional[dict]:
        """查找与列表页关联的下一页节点"""
        for node in self.nodes.values():
            if node["node_type"] == "next":
                # 下一页节点的回调指向当前列表页，或者就在同一个项目中
                if node.get("callback_node_id") == list_node_config["_id"]:
                    return node
        # 如果没有明确的回调指向，查找项目中的下一页节点
        for node in self.nodes.values():
            if node["node_type"] == "next":
                return node
        return None

    async def _handle_next_result(self, result: NodeResult, context: CrawlContext):
        """处理下一页结果：循环回调"""
        if self._stop_flag:
            return

        if result.next_url and result.callback_node_id:
            try:
                headers = context.headers
                cookies = context.cookies
                response = await fetch(
                    url=result.next_url,
                    headers=headers,
                    cookies=cookies,
                )
                next_context = context.clone(
                    url=result.next_url,
                    html=response.text,
                )
                await self._execute_node(result.callback_node_id, next_context)
            except Exception as e:
                logger.warning("下一页请求失败: %s", e)

    async def validate(self) -> list[str]:
        """
        验证工作流合法性

        Returns:
            错误信息列表，空列表表示合法
        """
        errors = []
        await self.load_nodes()

        if not self.nodes:
            errors.append("项目没有配置任何节点")
            return errors

        # 检查起始节点
        start_node = self.get_start_node()
        if not start_node:
            errors.append("缺少起始页节点")

        # 检查悬空的 callback 引用
        for node in self.nodes.values():
            cb_id = node.get("callback_node_id")
            if cb_id and cb_id not in self.nodes:
                errors.append(
                    f"节点 [{node['name']}] 的回调目标 {cb_id} 不存在"
                )

        # 检查详情页节点是否有 callback（不应该有）
        for node in self.nodes.values():
            if node["node_type"] == "detail" and node.get("callback_node_id"):
                errors.append(
                    f"详情页节点 [{node['name']}] 不应配置回调目标"
                )

        return errors
