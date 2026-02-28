"""
RuleCrawl 消息代理 (Broker) 抽象层
支持 RabbitMQ / Redis / Memory 等多种实现
"""

import asyncio
import json
import dataclasses
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, AsyncIterator, Callable
import aio_pika
from app.engine.context import TaskContext
from app.utils.logger import get_logger

logger = get_logger("core.broker")

class BaseBroker(ABC):
    """消息代理基类"""
    @abstractmethod
    async def connect(self): pass

    @abstractmethod
    async def close(self): pass

    @abstractmethod
    async def enqueue_task(self, project_id: str, node_id: str, context: TaskContext):
        """发送采集任务"""
        pass

    @abstractmethod
    async def consume_tasks(self, project_id: str) -> AsyncIterator[tuple[str, TaskContext]]:
        """消费采集任务"""
        yield # type: ignore

    @abstractmethod
    async def get_message_count(self, project_id: str) -> int:
        """获取队列积压数"""
        pass

    @abstractmethod
    async def delete_queue(self, project_id: str):
        """物理删除项目队列"""
        pass

    @abstractmethod
    async def broadcast_control(self, task_id: str, action: str):
        """发布控制信号 (停止等)"""
        pass

    @abstractmethod
    async def listen_controls(self, task_id: str, callback: Callable):
        """监听控制信号"""
        pass

class RabbitMQBroker(BaseBroker):
    """基于 RabbitMQ 的工业级 Broker 实现"""
    def __init__(self, url: str):
        self.url = url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.control_exchange_name = "rulecrawl_controls"

    async def connect(self):
        if not self.connection or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
            # 声明控制交换机
            self.control_exchange = await self.channel.declare_exchange(
                self.control_exchange_name, aio_pika.ExchangeType.FANOUT
            )
            logger.info("RabbitMQ Broker 已连接")

    async def close(self):
        if self.connection: await self.connection.close()

    def _get_q_name(self, project_id: str): return f"project_{project_id}"

    async def enqueue_task(self, project_id: str, node_id: str, context: TaskContext):
        q_name = self._get_q_name(project_id)
        payload = json.dumps({
            "node_id": node_id, 
            "context": dataclasses.asdict(context)
        }, ensure_ascii=False).encode()
        
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=payload, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=q_name
        )

    async def consume_tasks(self, project_id: str) -> AsyncIterator[tuple[str, TaskContext]]:
        q_name = self._get_q_name(project_id)
        queue = await self.channel.declare_queue(q_name, durable=True)
        async with queue.iterator() as q_iter:
            async for message in q_iter:
                async with message.process():
                    data = json.loads(message.body.decode())
                    yield data["node_id"], TaskContext(**data["context"])

    async def get_message_count(self, project_id: str) -> int:
        q_name = self._get_q_name(project_id)
        queue = await self.channel.declare_queue(q_name, durable=True)
        return queue.declaration_result.message_count

    async def delete_queue(self, project_id: str):
        await self.channel.queue_delete(self._get_q_name(project_id))

    async def broadcast_control(self, task_id: str, action: str):
        payload = json.dumps({"task_id": task_id, "action": action}).encode()
        await self.control_exchange.publish(aio_pika.Message(body=payload), routing_key="")

    async def listen_controls(self, task_id: str, callback: Callable):
        queue = await self.channel.declare_queue("", exclusive=True)
        await queue.bind(self.control_exchange)
        async with queue.iterator() as q_iter:
            async for message in q_iter:
                async with message.process():
                    sig = json.loads(message.body.decode())
                    if sig.get("task_id") == task_id:
                        await callback(sig.get("action"))
