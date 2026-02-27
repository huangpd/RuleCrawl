"""
工作流管理器 (Flow Manager) - 工业级分布式版
针对 aio-pika 全版本进行的严谨适配，确保 message_count 获取路径正确。
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
from app.engine.nodes.start import StartNode
from app.engine.nodes.list_page import ListPageNode
from app.engine.nodes.detail import DetailNode
from app.config import MAX_CONCURRENT_REQUESTS, RABBITMQ_URL

logger = get_logger(__name__)

NODE_CLASS_MAP = {"start": StartNode, "list": ListPageNode, "detail": DetailNode}

class FlowManager:
    def __init__(self, project_id: str, task_id: str):
        self.project_id, self.task_id = project_id, task_id
        self.nodes: Dict[str, dict] = {}
        self._stop_flag = False
        self._rmq_conn: Optional[aio_pika.RobustConnection] = None
        self._rmq_channel: Optional[aio_pika.Channel] = None
        self._task_queue_name = f"project_{project_id}"
        self._control_exchange_name = "rulecrawl_controls"

    async def _setup_mq(self):
        """初始化 MQ 连接和基础结构"""
        self._rmq_conn = await aio_pika.connect_robust(RABBITMQ_URL)
        self._rmq_channel = await self._rmq_conn.channel()
        await self._rmq_channel.set_qos(prefetch_count=MAX_CONCURRENT_REQUESTS)
        
        # 声明信号总线
        self._control_exchange = await self._rmq_channel.declare_exchange(
            self._control_exchange_name, aio_pika.ExchangeType.FANOUT
        )
        control_queue = await self._rmq_channel.declare_queue("", exclusive=True)
        await control_queue.bind(self._control_exchange)
        asyncio.create_task(self._listen_controls(control_queue))

    async def _get_queue_message_count(self) -> int:
        """安全地获取队列中的待处理消息数"""
        # 重新声明同一个持久化队列是获取 message_count 的标准异步方式
        temp_q = await self._rmq_channel.declare_queue(self._task_queue_name, durable=True)
        return temp_q.declaration_result.message_count

    async def _listen_controls(self, queue: aio_pika.Queue):
        """控制信号监听"""
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
        """任务入队"""
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

            # 1. 检查队列状态
            msg_count = await self._get_queue_message_count()
            
            if msg_count == 0:
                start_node = next((n for n in self.nodes.values() if n["node_type"] == "start"), None)
                if not start_node: raise ValueError("缺少起始节点")
                await self._enqueue(start_node["_id"], CrawlContext(project_id=self.project_id, task_id=self.task_id))
                logger.info(f"新任务初始化成功: {self.task_id}")
            else:
                logger.info(f"检测到存量任务 (%d 条)，执行断点续爬", msg_count)

            # 2. 启动分布式 Worker
            workers = [asyncio.create_task(self._worker()) for _ in range(MAX_CONCURRENT_REQUESTS)]
            
            # 3. 监控循环
            is_natural_finish = False
            while not self._stop_flag:
                await asyncio.sleep(5)
                if (await self._get_queue_message_count()) == 0:
                    # 队列清空后双重确认
                    await asyncio.sleep(5)
                    if (await self._get_queue_message_count()) == 0:
                        is_natural_finish = True
                        break

            # 只有在非自然完成的情况下才调用 stop() (即手动触发或异常)
            if not is_natural_finish:
                self.stop()
            
            for w in workers: w.cancel()
            
            # 状态判定：如果是因为队列空了而退出，则是 completed
            final_status = "completed" if is_natural_finish else "stopped"
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": final_status, "finished_at": datetime.now(timezone.utc)}})
            
            # 只有当采集任务【自然完成】时，才清理 MQ 队列
            if is_natural_finish:
                await self._rmq_channel.queue_delete(self._task_queue_name)
                logger.info(f"项目采集任务全部完成，清理队列: {self.project_id}")
            else:
                logger.info(f"任务已接收停止信号或异常中断，保留队列以支持断点续爬: {self.project_id}")

        except Exception as e:
            logger.error(f"引擎崩溃: {e}", exc_info=True)
            await db.tasks.update_one({"_id": self.task_id}, {"$set": {"status": "failed", "error_message": str(e)}})
        finally:
            if self._rmq_conn: await self._rmq_conn.close()

    async def _worker(self):
        """Worker 协程"""
        # 获取任务队列引用
        queue = await self._rmq_channel.declare_queue(self._task_queue_name, durable=True)
        try:
            async with queue.iterator() as q_iter:
                async for message in q_iter:
                    if self._stop_flag: break
                    async with message.process():
                        data = json.loads(message.body.decode())
                        await self._run_node(data["node_id"], CrawlContext(**data["context"]))
        except asyncio.CancelledError: pass
        except Exception as e: logger.error(f"Worker 运行时异常: {e}")

    async def _run_node(self, node_id: str, context: CrawlContext):
        config = self.nodes.get(node_id)
        if not config: return
        # 核心：使用 Pydantic 类型作为唯一事实来源
        node = NODE_CLASS_MAP[config["node_type"]](NodeCreate(**config).model_dump())
        res = await node.execute(context)
        db = get_db()
        
        if not res.success:
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.errors": 1}})
            return

        await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_requests": 1}})
        ctx = res.context or context

        if config["node_type"] == "detail":
            await db.tasks.update_one({"_id": self.task_id}, {"$inc": {"stats.total_items": 1}})
        elif config["node_type"] == "list":
            if res.callback_node_id:
                for url in res.urls:
                    data = ctx.parent_data.copy()
                    data.update(res.url_data.get(url, {}))
                    await self._enqueue(res.callback_node_id, ctx.clone(url=url, html="", parent_data=data))
                for item in res.items:
                    await self._enqueue(res.callback_node_id, ctx.clone(url=f"data://{uuid.uuid4()}", html=json.dumps(item), content_type="json"))
            if res.next_url:
                await self._enqueue(node_id, ctx.clone(url=res.next_url, html="", page_number=ctx.page_number + 1))
        elif config["node_type"] == "start":
            if res.callback_node_id:
                for url in (res.urls or [ctx.url]):
                    await self._enqueue(res.callback_node_id, ctx.clone(url=url, html="" if res.urls else ctx.html))

    def stop(self): self._stop_flag = True
    async def validate(self) -> list: return []
