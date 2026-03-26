from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        发送对话消息并返回 LLM 文本回复。
        messages: OpenAI 格式 [{"role": "user", "content": "..."}]
        system_prompt: 覆盖本次调用的系统提示（可选）
        """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算文本 token 数，用于 Token Budget 控制。"""
