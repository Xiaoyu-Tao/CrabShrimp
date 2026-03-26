from typing import TYPE_CHECKING, List, Optional
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.agent_profile import AgentProfile, ExecMode, RoleType, WorkspaceMode
from crabshrimp.tidal_pool.sandbox import LocalSandbox, SubprocessSandbox
from .base import BaseAgent
from .roles.planner import PlannerAgent
from .roles.executor import ExecutorAgent
from .roles.critic import CriticAgent
from .roles.verifier import VerifierAgent
from .roles.summarizer import SummarizerAgent

if TYPE_CHECKING:
    from crabshrimp.config import CrabShrimpConfig
    from crabshrimp.db.optimization_repo import OptimizationRepository
    from crabshrimp.db.skill_repo import SkillRepository
    from crabshrimp.tidal_pool.workspace import WorkspaceManager

_ROLE_MAP = {
    RoleType.planner: PlannerAgent,
    RoleType.executor: ExecutorAgent,
    RoleType.critic: CriticAgent,
    RoleType.verifier: VerifierAgent,
    RoleType.summarizer: SummarizerAgent,
}


class AgentFactory:
    def __init__(
        self,
        llm_client: BaseLLMClient,
        workspace_manager: Optional["WorkspaceManager"] = None,
        config: Optional["CrabShrimpConfig"] = None,
        skill_repo: Optional["SkillRepository"] = None,
        optimization_repo: Optional["OptimizationRepository"] = None,
    ):
        self._llm_client = llm_client
        self._workspace_manager = workspace_manager
        self._config = config
        self._skill_repo = skill_repo
        self._optimization_repo = optimization_repo

    def create(
        self,
        profile: AgentProfile,
        task_category: str = "general",
    ) -> BaseAgent:
        workspace_dir = None
        sandbox = None

        if self._config and self._workspace_manager:
            # 工作空间隔离
            if (
                self._config.workspace_isolation_enabled
                and profile.workspace_mode == WorkspaceMode.scoped
            ):
                workspace_dir = self._workspace_manager.get_or_create(profile.agent_id)

            # 执行环境隔离（依赖工作空间）
            if workspace_dir is not None and self._config.exec_isolation_enabled:
                if profile.exec_mode == ExecMode.subprocess:
                    sandbox = SubprocessSandbox(workspace_dir)
                else:
                    sandbox = LocalSandbox()
            elif workspace_dir is not None:
                sandbox = LocalSandbox()

        # Skill 注入：从知识库取历史 Skill，拼接到 system_prompt 末尾，并更新 usage_count
        injected_profile = profile
        if (
            self._skill_repo is not None
            and self._config is not None
            and self._config.skill_injection_enabled
        ):
            skill_pairs: List[tuple] = self._skill_repo.get_top_skills(
                role=profile.role.value.lower(),
                task_category=task_category,
                limit=3,
            )
            if skill_pairs:
                skill_block = "\n\n## Learned Skills (apply when relevant)\n" + "\n".join(
                    f"- {content}" for _, content in skill_pairs
                )
                injected_profile = profile.model_copy(
                    update={"system_prompt": profile.system_prompt + skill_block}
                )
                # 反馈使用次数，让高频有效的 Skill 保持排名靠前
                for skill_id, _ in skill_pairs:
                    self._skill_repo.increment_usage(skill_id)

        # Prompt 优化注入：将历史优化建议追加到 system_prompt
        if (
            self._optimization_repo is not None
            and self._config is not None
            and self._config.optimizer_enabled
        ):
            opt_pairs = self._optimization_repo.get_top(
                role=profile.role.value.lower(),
                task_category=task_category,
                limit=1,
            )
            if opt_pairs:
                opt_block = "\n\n## Prompt Optimization Note\n" + "\n".join(
                    f"- {patch}" for _, patch in opt_pairs
                )
                injected_profile = injected_profile.model_copy(
                    update={"system_prompt": injected_profile.system_prompt + opt_block}
                )
                for opt_id, _ in opt_pairs:
                    self._optimization_repo.increment_usage(opt_id)

        cls = _ROLE_MAP.get(profile.role)
        if cls is None:
            raise ValueError(f"Unknown role: {profile.role}")
        return cls(
            profile=injected_profile,
            llm_client=self._llm_client,
            workspace_dir=workspace_dir,
            sandbox=sandbox,
        )
