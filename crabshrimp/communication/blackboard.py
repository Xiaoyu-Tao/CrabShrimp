import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional
from crabshrimp.models.message import Message


class AsyncBlackboard:
    """
    内存模拟黑板（异步），v0.2 替换为 Redis。
    支持 KV 状态共享 + 主题消息订阅。
    """

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._topics: Dict[str, List[Message]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, message: Message) -> None:
        async with self._lock:
            self._topics[topic].append(message)

    async def subscribe(self, topic: str) -> List[Message]:
        async with self._lock:
            messages = list(self._topics.get(topic, []))
            self._topics[topic].clear()
            return messages

    async def set_state(self, key: str, value: Any) -> None:
        async with self._lock:
            self._state[key] = value

    async def get_state(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._state.get(key)
