from typing import Dict, List, Optional
import litellm
from .base import BaseLLMClient


class LiteLLMClient(BaseLLMClient):
    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_base: Optional[str] = None,
        max_retries: int = 3,
        timeout: float = 120.0,
        **litellm_kwargs,
    ):
        """
        model: LiteLLM 格式的模型标识符
               Claude:  "claude-sonnet-4-6"
               OpenAI:  "gpt-4o"
               开源:    "ollama/llama3"
        """
        self.model = model
        self.api_base = api_base
        self.max_retries = max_retries
        self.timeout = timeout
        self._litellm_kwargs = litellm_kwargs

    async def complete(
        self,
        messages: List[Dict],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        extra = {**self._litellm_kwargs, **kwargs}
        if self.api_base:
            extra["api_base"] = self.api_base

        response = await litellm.acompletion(
            model=self.model,
            messages=full_messages,
            num_retries=self.max_retries,
            timeout=self.timeout,
            **extra,
        )
        return response.choices[0].message.content

    def count_tokens(self, text: str) -> int:
        try:
            return litellm.token_counter(model=self.model, text=text)
        except Exception:
            return len(text) // 4  # 粗略估算兜底
