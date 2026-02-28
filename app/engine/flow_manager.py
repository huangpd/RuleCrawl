"""
工作流管理器 (Flow Manager) - 架构进化版 (V2)
1. 实现了任务上下文与响应内容的物理分离
2. 彻底杜绝了 StartNode 导致的重复下载隐患
3. 遵循 Pydantic 字典访问规范
"""

import asyncio
import json
import uuid
import dataclasses
from datetime import datetime, timezone
from typing import Optional, Dict

from app.utils.logger import get_logger
from app.database import get_db
from app.models.node import NodeCreate
from app.engine.context import TaskContext
from app.engine.nodes.base import NodeRegistry
import app.engine.nodes # 触发自注册
from app.core.broker import BaseBroker, RabbitMQBroker
from app.config import MAX_CONCURRENT_REQUESTS, RABBITMQ_URL

logger = get_logger(__name__)

class FlowManager:
    def __init__(self, project_id: str, task_id: str, broker: Optional[BaseBroker] = None):
        self.project_id, self.task_id = project_id, task_id
        self.nodes: Dict[str, dict] = {}
        self._stop_flag = False
        self.broker = broker or RabbitMQBroker(RABBITMQ_URL)
        self._control_task: Optional[asyncio.Task] = None

    async def execute(self):
        db = get_db()
        await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": "running", "started_at": datetime.now(timezone.utc)}})

        try:
            await self.broker.connect()
            cursor = db.nodes.find({"project_id": self.project_id})
            async for doc in cursor: self.nodes[doc["_id"]] = doc

            self._control_task = asyncio.create_task(self.broker.listen_controls(self.task_id, self._on_control_signal))

            # 1. 检查断点续爬
            if await self.broker.get_message_count(self.project_id) == 0:
                start_node = next((n for n in self.nodes.values() if n["node_type"] == "start"), None)
                if not start_node: raise ValueError("项目缺少起始节点")
                
                seed_ctx = TaskContext(url="", project_id=self.project_id, task_id=self.task_id)
                await self.broker.enqueue_task(self.project_id, start_node["_id"], seed_ctx)
                logger.info(f"任务初始化: {self.task_id}")

            workers = [asyncio.create_task(self._worker()) for _ in range(MAX_CONCURRENT_REQUESTS)]
            
            is_natural_finish = False
            while not self._stop_flag:
                await asyncio.sleep(5)
                if await self.broker.get_message_count(self.project_id) == 0:
                    await asyncio.sleep(5)
                    if await self.broker.get_message_count(self.project_id) == 0:
                        is_natural_finish = True
                        break

            self.stop()
            for w in workers: w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            
            status = "completed" if is_natural_finish else "stopped"
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": status, "finished_at": datetime.now(timezone.utc)}})
            
            # ── 核心修复：自然完成后清理队列 ──
            if is_natural_finish:
                logger.info(f"任务正常结束，清理项目队列: {self.project_id}")
                if hasattr(self.broker, "delete_queue"):
                    await self.broker.delete_queue(self.project_id)
            else:
                logger.info(f"任务手动停止或异常中断，保留队列以支持断点续爬: {self.project_id}")

        except Exception as e:
            logger.error(f"引擎崩溃: {e}", exc_info=True)
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": "failed", "error_message": str(e)}})
        finally:
            if self._control_task: self._control_task.cancel()
            await self.broker.close()

    async def _on_control_signal(self, action: str):
        if action == "STOP": self.stop()

    async def _worker(self):
        try:
            async for node_id, context in self.broker.consume_tasks(self.project_id):
                if self._stop_flag: break
                try:
                    await self._run_node(node_id, context)
                except Exception as task_err:
                    logger.error(f"任务执行异常: {task_err}")
        except asyncio.CancelledError: pass

    async def _run_node(self, node_id: str, context: TaskContext):
        config = self.nodes.get(node_id)
        if not config: return
        
        node_cls = NodeRegistry.get_node_class(config["node_type"])
        if not node_cls: return
        
        # 核心：使用 Pydantic 字典作为实例输入
        validated_config = NodeCreate(**config).model_dump()
        node = node_cls(validated_config)
        db = get_db()
        
        # 1. 流量调度
        response = None
        if context.url.startswith("data://"):
            from app.models.download import DownloadResponse
            response = DownloadResponse(
                url=context.url, status_code=200, 
                text=context.parent_data.get("_virtual_html", ""), 
                content_type="json"
            )
        elif validated_config["node_type"] in ["list", "detail"]:
            try:
                if not context.url: raise ValueError(f"节点 [{config['name']}] 缺少 URL")
                downloader = await node.get_downloader()
                req_args = node.merge_request_args(context)
                response = await downloader.fetch(context.url, **req_args)
            except Exception as e:
                logger.error(f"下载失败: {context.url} - {e}")
                await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.errors": 1}})
                return

        # 2. 执行业务
        res = await node.execute(context, response)
        if not res.success:
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.errors": 1}})
            return

        if response:
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_requests": 1}})
        if validated_config["node_type"] == "detail":
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_items": 1}})

        # 3. 分发
        for next_node_id, next_context in res.follow_up_tasks:
            await self.broker.enqueue_task(self.project_id, next_node_id, next_context)

    def stop(self): self._stop_flag = True
    async def validate(self) -> list: return []
