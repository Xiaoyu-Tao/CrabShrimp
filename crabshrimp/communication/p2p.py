import asyncio
from collections import defaultdict
from typing import Dict
from crabshrimp.models.message import Message


class SyncP2P:
    """
    同步点对点消息传递，用于 Coral-Meeting 辩论轮次。
    内存队列实现，等待对方回复后再继续。
    """

    def __init__(self):
        self._inboxes: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def send(self, to_agent_id: str, message: Message) -> None:
        await self._inboxes[to_agent_id].put(message)

    async def receive(self, agent_id: str, timeout: float = 30.0) -> Message:
        """阻塞等待收件箱，超时抛出 asyncio.TimeoutError。"""
        return await asyncio.wait_for(
            self._inboxes[agent_id].get(), timeout=timeout
        )
