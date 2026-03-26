from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.agent_profile import AgentProfile
from crabshrimp.tidal_pool.sandbox import SandboxInterface


class BaseAgent(ABC):
    def __init__(
        self,
        profile: AgentProfile,
        llm_client: BaseLLMClient,
        workspace_dir: Optional[Path] = None,
        sandbox: Optional[SandboxInterface] = None,
    ):
        self.profile = profile
        self.llm_client = llm_client
        self._conversation_history: List[Dict] = []
        self.workspace_dir = workspace_dir   # Path | None，由 WorkspaceManager 分配
        self.sandbox = sandbox               # SandboxInterface | None，由 AgentFactory 注入

    @property
    def agent_id(self) -> str:
        return self.profile.agent_id

    @property
    def role(self) -> str:
        return self.profile.role.value

    @abstractmethod
    async def think(self, input_text: str) -> str:
        """核心推理：接收输入，返回推理过程文本（CoT）。"""

    @abstractmethod
    async def act(self, task_context: dict) -> dict:
        """
        执行动作：返回包含 reasoning 和 output 的字典。
        格式: {"reasoning": "...", "output": "...", "result": "success|failure"}
        """

    def request_meeting(self, reason: str) -> bool:
        """Agent 主动请求触发 Coral-Meeting，返回 True 表示已发出请求。"""
        self._meeting_request = reason
        return True

    def has_meeting_request(self) -> bool:
        return hasattr(self, "_meeting_request") and bool(self._meeting_request)

    def clear_meeting_request(self) -> str:
        reason = getattr(self, "_meeting_request", "")
        self._meeting_request = ""
        return reason
