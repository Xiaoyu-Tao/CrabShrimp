from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional
from crabshrimp.models.agent_profile import (
    AgentProfile, ContextMode, ExecMode, RoleType, WorkspaceMode,
)

if TYPE_CHECKING:
    from crabshrimp.db.agent_repo import AgentRepository

_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"


def _load_prompt(filename: str) -> str:
    path = _PROMPT_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"You are a {filename.replace('.txt', '')} agent."


_DEFAULT_PROFILES: Dict[RoleType, dict] = {
    RoleType.planner: dict(
        agent_id="planner-001",
        prompt_file="planner.txt",
        context_mode=ContextMode.shared,
        workspace_mode=WorkspaceMode.none,
        exec_mode=ExecMode.local,
    ),
    RoleType.executor: dict(
        agent_id="executor-001",
        prompt_file="executor.txt",
        context_mode=ContextMode.shared,
        workspace_mode=WorkspaceMode.scoped,
        exec_mode=ExecMode.subprocess,
    ),
    RoleType.critic: dict(
        agent_id="critic-001",
        prompt_file="critic.txt",
        context_mode=ContextMode.isolated,
        workspace_mode=WorkspaceMode.none,
        exec_mode=ExecMode.local,
    ),
    RoleType.verifier: dict(
        agent_id="verifier-001",
        prompt_file="verifier.txt",
        context_mode=ContextMode.isolated,
        workspace_mode=WorkspaceMode.none,
        exec_mode=ExecMode.local,
    ),
    RoleType.summarizer: dict(
        agent_id="summarizer-001",
        prompt_file="summarizer.txt",
        context_mode=ContextMode.shared,
        workspace_mode=WorkspaceMode.none,
        exec_mode=ExecMode.local,
    ),
}


class AgentRegistry:
    """
    Agent 档案中心。
    - agent_repo=None：纯内存模式（测试 / 快速启动）
    - agent_repo 传入时：SQLite 持久化，contribution_score 跨任务保留
    """

    def __init__(self, agent_repo: Optional["AgentRepository"] = None):
        self._profiles: Dict[str, AgentProfile] = {}
        self._repo = agent_repo
        # 启动时从 DB 加载已有档案
        if agent_repo:
            for profile in agent_repo.load_all():
                self._profiles[profile.agent_id] = profile

    def register(self, profile: AgentProfile) -> None:
        self._profiles[profile.agent_id] = profile
        if self._repo:
            self._repo.save(profile)

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        return self._profiles.get(agent_id)

    def list_by_role(self, role: RoleType) -> List[AgentProfile]:
        return sorted(
            [p for p in self._profiles.values() if p.role == role],
            key=lambda p: p.contribution_score,
            reverse=True,
        )

    def update_contribution(self, agent_id: str, delta: float) -> None:
        if profile := self._profiles.get(agent_id):
            profile.contribution_score = max(0.0, profile.contribution_score + delta)
            if self._repo:
                self._repo.update_contribution(agent_id, profile.contribution_score)

    def seed_defaults(self) -> None:
        """
        填充预设角色。
        若 DB 中已有该 agent_id（历史运行保留的档案），跳过插入，保留已有 contribution_score。
        """
        for role, cfg in _DEFAULT_PROFILES.items():
            agent_id = cfg["agent_id"]
            if agent_id in self._profiles:
                # 已从 DB 加载，跳过（保留历史 contribution_score）
                continue
            self.register(
                AgentProfile(
                    agent_id=agent_id,
                    role=role,
                    system_prompt=_load_prompt(cfg["prompt_file"]),
                    context_mode=cfg["context_mode"],
                    workspace_mode=cfg["workspace_mode"],
                    exec_mode=cfg["exec_mode"],
                )
            )
