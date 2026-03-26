"""
v0.2b Shell-Molting 演化引擎测试
- Coral-Meeting winner → +0.10
- Verifier failure → 上游 Agent -0.15
- Critic rejected  → 上游 Agent -0.10
- stopped_early    → 全员 -0.05
- 归因逻辑：跳过评估者，找最近上游生产者
- Critic ACCEPTABLE / REJECTED 解析
"""
import sqlite3
from typing import List

from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.db.agent_repo import AgentRepository
from crabshrimp.db.connection import get_connection
from crabshrimp.db.meeting_repo import MeetingRepository
from crabshrimp.models.agent_profile import AgentProfile, RoleType
from crabshrimp.models.trace import TraceStep
from crabshrimp.tidal_pool.shell_molting import ShellMolting, _find_upstream


# ── 工具函数 ──────────────────────────────────────────────────

def _make_db():
    conn = get_connection(":memory:")
    return conn, AgentRepository(conn), MeetingRepository(conn)


def _step(agent_id: str, result: str, task_id: str = "t1") -> TraceStep:
    return TraceStep(
        task_id=task_id, agent_id=agent_id,
        input="x", reasoning="r", output="o", result=result,
    )


def _registry(conn) -> AgentRegistry:
    repo = AgentRepository(conn)
    registry = AgentRegistry(agent_repo=repo)
    registry.seed_defaults()
    return registry


# ── _find_upstream ────────────────────────────────────────────

def test_find_upstream_skips_evaluators():
    steps = [
        _step("executor-001", "success"),
        _step("critic-001",   "rejected"),
    ]
    assert _find_upstream(steps, 1) == "executor-001"


def test_find_upstream_skips_coral_meeting():
    steps = [
        _step("executor-001", "success"),
        _step("coral-meeting", "success"),
        _step("verifier-001", "failure"),
    ]
    assert _find_upstream(steps, 2) == "executor-001"


def test_find_upstream_returns_none_if_no_producer():
    steps = [_step("verifier-001", "failure")]
    assert _find_upstream(steps, 0) is None


# ── ShellMolting 规则 ─────────────────────────────────────────

def test_meeting_winner_rewarded():
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)
    meeting_repo.save_outcome("t1", "s1", "critic-001", "topic")

    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", [], stopped_early=False)

    assert abs(deltas.get("critic-001", 0) - 0.10) < 1e-6
    assert abs(registry.list_by_role(RoleType.critic)[0].contribution_score - 1.10) < 1e-6


def test_verifier_failure_punishes_upstream():
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)

    steps = [
        _step("executor-001", "success"),
        _step("verifier-001", "failure"),
    ]
    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", steps, stopped_early=False)

    assert abs(deltas.get("executor-001", 0) - (-0.15)) < 1e-6
    score = registry.list_by_role(RoleType.executor)[0].contribution_score
    assert abs(score - 0.85) < 1e-6


def test_critic_rejected_punishes_upstream():
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)

    steps = [
        _step("executor-001", "success"),
        _step("critic-001",   "rejected"),
    ]
    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", steps, stopped_early=False)

    assert abs(deltas.get("executor-001", 0) - (-0.10)) < 1e-6


def test_stopped_early_punishes_all_producers():
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)

    steps = [
        _step("planner-001",  "success"),
        _step("executor-001", "success"),
    ]
    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", steps, stopped_early=True)

    assert abs(deltas.get("planner-001",  0) - (-0.05)) < 1e-6
    assert abs(deltas.get("executor-001", 0) - (-0.05)) < 1e-6


def test_arbitrated_winner_none_gets_no_reward():
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)
    meeting_repo.save_outcome("t1", "s1", None, "topic")  # None = 仲裁

    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", [], stopped_early=False)

    # 没有任何 agent 获得奖励
    assert all(v == 0 for v in deltas.values()) or not deltas


def test_deltas_accumulate_correctly():
    """同一 Agent 同时赢得会议 (+0.10) 且上游被 Verifier 否定 (-0.15)，净值 -0.05。"""
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)
    meeting_repo.save_outcome("t1", "s1", "executor-001", "topic")

    steps = [
        _step("executor-001", "success"),
        _step("verifier-001", "failure"),
    ]
    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    deltas = sm.evolve("t1", steps, stopped_early=False)

    net = deltas.get("executor-001", 0)
    assert abs(net - (0.10 - 0.15)) < 1e-6


def test_score_never_goes_below_zero():
    """contribution_score 下限为 0。"""
    conn, agent_repo, meeting_repo = _make_db()
    registry = _registry(conn)

    # 连续 20 次被 Verifier 否定
    steps = []
    for _ in range(20):
        steps += [
            _step("executor-001", "success"),
            _step("verifier-001", "failure"),
        ]
    sm = ShellMolting(registry=registry, meeting_repo=meeting_repo)
    sm.evolve("t1", steps, stopped_early=False)

    score = registry.list_by_role(RoleType.executor)[0].contribution_score
    assert score >= 0.0


# ── Critic 真实判定 ───────────────────────────────────────────

def test_critic_result_rejected_when_keyword_present():
    """CriticAgent.act() 应在回复含 QUALITY: REJECTED 时返回 result=rejected。"""
    import asyncio
    from crabshrimp.agents.roles.critic import CriticAgent
    from crabshrimp.models.agent_profile import AgentProfile, RoleType

    class FakeLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            return "Flaw 1: X. Flaw 2: Y.\n\nQUALITY: REJECTED"
        def count_tokens(self, text): return 0

    profile = AgentProfile(agent_id="critic-001", role=RoleType.critic, system_prompt="")
    agent = CriticAgent(profile=profile, llm_client=FakeLLM())
    result = asyncio.run(agent.act({"output_to_review": "some output"}))
    assert result["result"] == "rejected"


def test_critic_result_success_when_acceptable():
    import asyncio
    from crabshrimp.agents.roles.critic import CriticAgent
    from crabshrimp.models.agent_profile import AgentProfile, RoleType

    class FakeLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            return "Minor issues found.\n\nQUALITY: ACCEPTABLE"
        def count_tokens(self, text): return 0

    profile = AgentProfile(agent_id="critic-001", role=RoleType.critic, system_prompt="")
    agent = CriticAgent(profile=profile, llm_client=FakeLLM())
    result = asyncio.run(agent.act({"output_to_review": "good output"}))
    assert result["result"] == "success"
