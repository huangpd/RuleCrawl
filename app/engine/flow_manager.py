"""
工作流管理器 (Flow Manager) - 工业级分布式版 (IoC 优化)
基于控制反转原则：节点决定生产什么任务，编排器只负责机械调度。
"""

import asyncio
import json
import uuid
import dataclasses
import aio_pika
from datetime import datetime, timezone
from typing import Optional, Dict

from app.utils.logger import get_logger
from app.database import get_db
from app.models.node import NodeCreate
from app.engine.context import CrawlContext
from app.engine.nodes.base import NodeRegistry
# 触发节点自注册
import app.engine.nodes
from app.utils.mq_client import get_mq_connection
from app.config import MAX_CONCURRENT_REQUESTS

logger = get_logger(__name__)

class FlowManager:
    def __init__(self, project_id: str, task_id: str):
        self.project_id, self.task_id = project_id, task_id
        self.nodes: Dict[str, dict] = {}
        self._stop_flag = False
        self._rmq_channel: Optional[aio_pika.Channel] = None
        self._task_queue_name = f"project_{project_id}"
        self._control_exchange_name = "rulecrawl_controls"
        self._control_task: Optional[asyncio.Task] = None

    async def _setup_mq(self):
        """初始化 MQ，通过全局连接建立 Channel"""
        connection = await get_mq_connection()
        self._rmq_channel = await connection.channel()
        await self._rmq_channel.set_qos(prefetch_count=MAX_CONCURRENT_REQUESTS)
        
        self._control_exchange = await self._rmq_channel.declare_exchange(
            self._control_exchange_name, aio_pika.ExchangeType.FANOUT
        )
        control_queue = await self._rmq_channel.declare_queue("", exclusive=True)
        await control_queue.bind(self._control_exchange)
        # 记录控制监听任务句柄
        self._control_task = asyncio.create_task(self._listen_controls(control_queue))

    async def _get_queue_message_count(self) -> int:
        temp_q = await self._rmq_channel.declare_queue(self._task_queue_name, durable=True)
        return temp_q.declaration_result.message_count

    async def _listen_controls(self, queue: aio_pika.Queue):
        try:
            async with queue.iterator() as q_iter:
                async for message in q_iter:
                    async with message.process():
                        sig = json.loads(message.body.decode())
                        if sig.get("task_id") == self.task_id and sig.get("action") == "STOP":
                            logger.warning(f"接收到停止信号，关停任务: {self.task_id}")
                            self.stop()
        except asyncio.CancelledError: pass

    async def _enqueue(self, node_id: str, context: CrawlContext):
        """核心入队方法：将任务状态持久化到 MQ"""
        payload = json.dumps({
            "node_id": node_id, 
            "context": dataclasses.asdict(context)
        }, ensure_ascii=False).encode()
        
        await self._rmq_channel.default_exchange.publish(
            aio_pika.Message(body=payload, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=self._task_queue_name
        )

    async def execute(self):
        db = get_db()
        await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": "running", "started_at": datetime.now(timezone.utc)}})

        try:
            await self._setup_mq()
            cursor = db.nodes.find({"project_id": self.project_id})
            async for doc in cursor: self.nodes[doc["_id"]] = doc

            # 1. 检查断点续爬
            msg_count = await self._get_queue_message_count()
            if msg_count == 0:
                start_node = next((n for n in self.nodes.values() if n["node_type"] == "start"), None)
                if not start_node: raise ValueError("项目缺少起始节点")
                await self._enqueue(start_node["_id"], CrawlContext(project_id=self.project_id, task_id=self.task_id))
                logger.info(f"新任务初始化成功: {self.task_id}")
            else:
                logger.info(f"断点续爬启动，存量任务: {msg_count}")

            # 2. 启动 Workers
            workers = [asyncio.create_task(self._worker()) for _ in range(MAX_CONCURRENT_REQUESTS)]
            
            # 3. 监控循环
            is_natural_finish = False
            while not self._stop_flag:
                await asyncio.sleep(5)
                if (await self._get_queue_message_count()) == 0:
                    await asyncio.sleep(5) # 二次确认
                    if (await self._get_queue_message_count()) == 0:
                        is_natural_finish = True
                        break

            if not is_natural_finish: self.stop()
            for w in workers: w.cancel()
            
            status = "completed" if is_natural_finish else "stopped"
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": status, "finished_at": datetime.now(timezone.utc)}})
            
            if is_natural_finish:
                await self._rmq_channel.queue_delete(self._task_queue_name)
                logger.info(f"任务自然完成，清理队列: {self.project_id}")
            else:
                logger.info(f"任务手动停止/异常，保留队列: {self.project_id}")

        except Exception as e:
            logger.error(f"引擎崩溃: {e}", exc_info=True)
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": "failed", "error_message": str(e)}})
        finally:
            # ── 核心修复：清理后台监听任务 ──
            if self._control_task:
                self._control_task.cancel()
                try:
                    await self._control_task
                except asyncio.CancelledError:
                    pass
            
            if self._rmq_channel: await self._rmq_channel.close()

    async def _worker(self):
        # 必须在 worker 内部重新声明队列以获得引用
        queue = await self._rmq_channel.declare_queue(self._task_queue_name, durable=True)
        try:
            async with queue.iterator() as q_iter:
                async for message in q_iter:
                    if self._stop_flag: break
                    try:
                        async with message.process():
                            data = json.loads(message.body.decode())
                            await self._run_node(data["node_id"], CrawlContext(**data["context"]))
                    except Exception as task_err:
                        logger.error(f"任务执行发生异常 (不中断连接): {task_err}")
        except asyncio.CancelledError: pass
        except Exception as e: logger.error(f"Worker 通道级异常: {e}")

    async def _run_node(self, node_id: str, context: CrawlContext):
        """执行节点并分发任务"""
        config = self.nodes.get(node_id)
        if not config: return
        
        # 利用 Pydantic 标准化配置
        validated_config = NodeCreate(**config).model_dump()
        node_cls = NodeRegistry.get_node_class(validated_config["node_type"])
        
        if not node_cls:
            logger.error(f"未注册的节点类型: {validated_config['node_type']}")
            return

        node = node_cls(validated_config)
        res = await node.execute(context)
        db = get_db()
        
        if not res.success:
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.errors": 1}})
            return

        # 通用记账：更新请求数
        await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_requests": 1}})
        
        # 特殊记账：如果是详情页，更新结果数
        if config["node_type"] == "detail":
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_items": 1}})

        # 核心：执行编排器的调度天职 —— 批量分发后续任务
        for next_node_id, next_context in res.follow_up_tasks:
            await self._enqueue(next_node_id, next_context)

    def stop(self): self._stop_flag = True
    async def validate(self) -> list: return []
