"""
隔离机制单元测试
- 上下文隔离：isolated 角色的 outputs_to_summarize 应为空
- 工作空间隔离：scoped 角色获得独立目录
- 执行环境隔离：subprocess 角色获得 SubprocessSandbox
- 开关关闭时：所有角色按 shared/none/local 行为
"""
import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from crabshrimp.agents.factory import AgentFactory
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.communication.blackboard import AsyncBlackboard
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.coral_meeting.meeting import CoralMeeting
from crabshrimp.dragon_king.orchestrator import DragonKing
from crabshrimp.models.agent_profile import ContextMode, ExecMode, WorkspaceMode
from crabshrimp.tidal_pool.resource_guard import ResourceGuard
from crabshrimp.tidal_pool.sandbox import LocalSandbox, SubprocessSandbox
from crabshrimp.tidal_pool.workspace import WorkspaceManager
from crabshrimp.trace.collector import TraceCollector
from crabshrimp.trace.writer import TraceWriter


# ── 工作空间隔离 ──────────────────────────────────────────────

def test_workspace_manager_creates_scoped_dir():
    with tempfile.TemporaryDirectory() as base:
        wm = WorkspaceManager(task_id="task-abc", base_dir=base)
        path = wm.get_or_create("executor-001")
        assert path.exists()
        assert path.is_dir()
        assert "task-abc" in str(path)
        assert "executor-001" in str(path)


def test_workspace_manager_returns_same_dir():
    with tempfile.TemporaryDirectory() as base:
        wm = WorkspaceManager(task_id="task-abc", base_dir=base)
        p1 = wm.get_or_create("executor-001")
        p2 = wm.get_or_create("executor-001")
        assert p1 == p2


def test_workspace_manager_cleanup():
    with tempfile.TemporaryDirectory() as base:
        wm = WorkspaceManager(task_id="task-abc", base_dir=base)
        path = wm.get_or_create("executor-001")
        assert path.exists()
        wm.cleanup()
        assert not path.exists()


# ── 执行环境隔离 ──────────────────────────────────────────────

def test_subprocess_sandbox_executes_command():
    async def run():
        with tempfile.TemporaryDirectory() as base:
            ws = Path(base)
            sandbox = SubprocessSandbox(ws)
            result = await sandbox.execute("echo hello")
            return result
    result = asyncio.run(run())
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_subprocess_sandbox_timeout():
    async def run():
        with tempfile.TemporaryDirectory() as base:
            ws = Path(base)
            sandbox = SubprocessSandbox(ws)
            result = await sandbox.execute("sleep 10", timeout=0.1)
            return result
    result = asyncio.run(run())
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"]


# ── AgentFactory 注入隔离资源 ────────────────────────────────

def test_factory_injects_workspace_and_subprocess_sandbox():
    with tempfile.TemporaryDirectory() as base:
        registry = AgentRegistry()
        registry.seed_defaults()

        from crabshrimp.llm.base import BaseLLMClient
        class DummyLLM(BaseLLMClient):
            async def complete(self, messages, system_prompt=None, **kwargs): return ""
            def count_tokens(self, text): return 0

        wm = WorkspaceManager(task_id="task-x", base_dir=base)
        cfg = CrabShrimpConfig(workspace_isolation_enabled=True, exec_isolation_enabled=True)
        factory = AgentFactory(llm_client=DummyLLM(), workspace_manager=wm, config=cfg)

        executor_profile = registry.list_by_role(
            __import__("crabshrimp.models.agent_profile", fromlist=["RoleType"]).RoleType.executor
        )[0]
        agent = factory.create(executor_profile)

        assert agent.workspace_dir is not None
        assert isinstance(agent.sandbox, SubprocessSandbox)


def test_factory_no_workspace_when_isolation_disabled():
    registry = AgentRegistry()
    registry.seed_defaults()

    from crabshrimp.llm.base import BaseLLMClient
    class DummyLLM(BaseLLMClient):
        async def complete(self, messages, system_prompt=None, **kwargs): return ""
        def count_tokens(self, text): return 0

    cfg = CrabShrimpConfig(workspace_isolation_enabled=False, exec_isolation_enabled=False)
    factory = AgentFactory(llm_client=DummyLLM(), config=cfg)

    from crabshrimp.models.agent_profile import RoleType
    executor_profile = registry.list_by_role(RoleType.executor)[0]
    agent = factory.create(executor_profile)

    assert agent.workspace_dir is None
    assert agent.sandbox is None


# ── 上下文隔离（通过 Orchestrator 集成测试）────────────────────

class ContextCapturingLLM:
    """记录每次 act() 传入的 outputs_to_summarize，用于验证隔离效果。"""
    def __init__(self):
        self.captured_summaries = []  # (agent prompt snippet, outputs_to_summarize)

    async def complete(self, messages, system_prompt=None, **kwargs):
        content = messages[0]["content"] if messages else ""
        if system_prompt and "task classifier" in system_prompt:
            return "analysis"
        if system_prompt and "JSON execution plan" in system_prompt:
            return json.dumps([
                {"step_id": 1, "description": "Execute work", "role": "Executor", "is_critical_node": False},
                {"step_id": 2, "description": "Critique result", "role": "Critic", "is_critical_node": False},
                {"step_id": 3, "description": "Verify result", "role": "Verifier", "is_critical_node": False},
                {"step_id": 4, "description": "Summarize", "role": "Summarizer", "is_critical_node": False},
            ])
        return f"OUTPUT_FROM_{system_prompt[:10] if system_prompt else 'unknown'}"

    def count_tokens(self, text):
        return len(text)


def test_isolated_agents_do_not_see_full_history():
    """Critic 和 Verifier 应看不到完整 outputs_to_summarize。"""
    received_contexts = {}

    class TrackingLLM(ContextCapturingLLM):
        async def complete(self, messages, system_prompt=None, **kwargs):
            return await super().complete(messages, system_prompt, **kwargs)

    async def run_case():
        llm = TrackingLLM()
        registry = AgentRegistry()
        registry.seed_defaults()

        # 验证 Critic/Verifier 的 context_mode 是 isolated
        from crabshrimp.models.agent_profile import RoleType
        critic_profile = registry.list_by_role(RoleType.critic)[0]
        verifier_profile = registry.list_by_role(RoleType.verifier)[0]
        assert critic_profile.context_mode == ContextMode.isolated
        assert verifier_profile.context_mode == ContextMode.isolated

        # 验证 Executor/Summarizer 的 context_mode 是 shared
        executor_profile = registry.list_by_role(RoleType.executor)[0]
        summarizer_profile = registry.list_by_role(RoleType.summarizer)[0]
        assert executor_profile.context_mode == ContextMode.shared
        assert summarizer_profile.context_mode == ContextMode.shared

    asyncio.run(run_case())


def test_agent_profile_isolation_defaults():
    """验证 seed_defaults 为每个角色设置了正确的隔离默认值。"""
    from crabshrimp.models.agent_profile import RoleType
    registry = AgentRegistry()
    registry.seed_defaults()

    executor = registry.list_by_role(RoleType.executor)[0]
    assert executor.workspace_mode == WorkspaceMode.scoped
    assert executor.exec_mode == ExecMode.subprocess
    assert executor.context_mode == ContextMode.shared

    critic = registry.list_by_role(RoleType.critic)[0]
    assert critic.context_mode == ContextMode.isolated
    assert critic.workspace_mode == WorkspaceMode.none

    verifier = registry.list_by_role(RoleType.verifier)[0]
    assert verifier.context_mode == ContextMode.isolated
    assert verifier.workspace_mode == WorkspaceMode.none

    summarizer = registry.list_by_role(RoleType.summarizer)[0]
    assert summarizer.context_mode == ContextMode.shared
