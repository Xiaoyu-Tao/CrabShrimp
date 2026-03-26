"""
v0.3 Skill 提取 & 拓扑调整测试
- SkillRepository CRUD
- RoleWeightRepository 胜率计算
- SkillExtractor 提取逻辑（FakeLLM）
- AgentFactory Skill 注入
- DragonKing 拓扑筛选（bench_threshold）
"""
import asyncio
from typing import List

import pytest

from crabshrimp.agents.factory import AgentFactory
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.db.agent_repo import AgentRepository
from crabshrimp.db.connection import get_connection
from crabshrimp.db.role_weight_repo import RoleWeightRepository
from crabshrimp.db.skill_repo import SkillRepository
from crabshrimp.evolution.skill_extractor import SkillExtractor
from crabshrimp.models.agent_profile import AgentProfile, RoleType
from crabshrimp.models.trace import TraceStep


# ── 工具函数 ──────────────────────────────────────────────────


def _make_db():
    conn = get_connection(":memory:")
    return conn, SkillRepository(conn), RoleWeightRepository(conn)


def _step(agent_id: str, result: str, reasoning: str = "good reasoning") -> TraceStep:
    return TraceStep(
        task_id="t1",
        agent_id=agent_id,
        input="do task",
        reasoning=reasoning,
        output="done",
        result=result,
    )


# ── SkillRepository ───────────────────────────────────────────


def test_skill_save_and_retrieve():
    conn, skill_repo, _ = _make_db()
    skill_repo.save("executor", "coding", "Use step-by-step decomposition.", "t1")
    pairs = skill_repo.get_top_skills("executor", "coding")
    assert len(pairs) == 1
    skill_id, content = pairs[0]
    assert "decomposition" in content


def test_skill_top_n_ordered_by_usage():
    conn, skill_repo, _ = _make_db()
    id1 = skill_repo.save("executor", "coding", "Skill A", "t1")
    id2 = skill_repo.save("executor", "coding", "Skill B", "t1")
    # Skill B used more
    skill_repo.increment_usage(id2)
    skill_repo.increment_usage(id2)
    pairs = skill_repo.get_top_skills("executor", "coding", limit=2)
    assert pairs[0][1] == "Skill B"  # index 1 = content


def test_skill_count_by_role_category():
    conn, skill_repo, _ = _make_db()
    skill_repo.save("planner", "analysis", "Plan carefully.", "t1")
    skill_repo.save("planner", "analysis", "Break into phases.", "t1")
    assert skill_repo.count_by_role_category("planner", "analysis") == 2
    assert skill_repo.count_by_role_category("executor", "analysis") == 0


def test_skill_no_cross_category_leak():
    conn, skill_repo, _ = _make_db()
    skill_repo.save("executor", "coding", "Skill C", "t1")
    assert skill_repo.get_top_skills("executor", "analysis") == []


# ── RoleWeightRepository ──────────────────────────────────────


def test_role_weight_new_agent_defaults_to_1():
    conn, _, rw_repo = _make_db()
    assert rw_repo.win_rate("coding", "executor", "executor-001") == 1.0


def test_role_weight_record_win():
    conn, _, rw_repo = _make_db()
    rw_repo.record_win("coding", "executor", "executor-001")
    rw_repo.record_win("coding", "executor", "executor-001")
    rw_repo.record_participation("coding", "executor", "executor-001")
    rate = rw_repo.win_rate("coding", "executor", "executor-001")
    assert abs(rate - 2 / 3) < 1e-6


def test_role_weight_record_participation_only():
    conn, _, rw_repo = _make_db()
    rw_repo.record_participation("coding", "executor", "executor-001")
    rw_repo.record_participation("coding", "executor", "executor-001")
    rate = rw_repo.win_rate("coding", "executor", "executor-001")
    assert rate == 0.0


def test_role_weight_no_cross_category_leak():
    conn, _, rw_repo = _make_db()
    rw_repo.record_win("coding", "executor", "executor-001")
    assert rw_repo.win_rate("analysis", "executor", "executor-001") == 1.0


# ── SkillExtractor ────────────────────────────────────────────


def test_skill_extractor_saves_success_steps():
    conn, skill_repo, _ = _make_db()

    class FakeLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            return "Break the problem into smaller steps."
        def count_tokens(self, text): return 0

    extractor = SkillExtractor(llm_client=FakeLLM(), skill_repo=skill_repo)
    steps = [
        _step("executor-001", "success"),
        _step("verifier-001", "failure"),  # 评估者，应跳过
        _step("critic-001", "rejected"),   # 评估者，应跳过
    ]
    saved = asyncio.run(extractor.extract_and_save("t1", "coding", steps))
    assert saved == 1


def test_skill_extractor_skips_na_response():
    conn, skill_repo, _ = _make_db()

    class FakeLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            return "N/A"
        def count_tokens(self, text): return 0

    extractor = SkillExtractor(llm_client=FakeLLM(), skill_repo=skill_repo)
    steps = [_step("planner-001", "success")]
    saved = asyncio.run(extractor.extract_and_save("t1", "coding", steps))
    assert saved == 0


def test_skill_extractor_respects_max_slots():
    conn, skill_repo, _ = _make_db()
    # 预填满槽（MAX_SKILLS_PER_SLOT = 10）
    for i in range(10):
        skill_repo.save("executor", "coding", f"Skill {i}", "t0")

    class FakeLLM:
        async def complete(self, messages, system_prompt=None, **kwargs):
            return "A new skill."
        def count_tokens(self, text): return 0

    extractor = SkillExtractor(llm_client=FakeLLM(), skill_repo=skill_repo)
    steps = [_step("executor-001", "success")]
    saved = asyncio.run(extractor.extract_and_save("t1", "coding", steps))
    assert saved == 0


# ── AgentFactory Skill 注入 ───────────────────────────────────


def test_factory_injects_skills_into_system_prompt():
    conn = get_connection(":memory:")
    skill_repo = SkillRepository(conn)
    agent_repo = AgentRepository(conn)
    skill_repo.save("executor", "coding", "Always validate inputs.", "t0")

    registry = AgentRegistry(agent_repo=agent_repo)
    registry.seed_defaults()

    class FakeLLM:
        def count_tokens(self, text): return 0

    cfg = CrabShrimpConfig(skill_injection_enabled=True)
    factory = AgentFactory(llm_client=FakeLLM(), config=cfg, skill_repo=skill_repo)
    profiles = registry.list_by_role(RoleType.executor)
    agent = factory.create(profiles[0], task_category="coding")
    assert "Always validate inputs." in agent.profile.system_prompt


def test_factory_no_injection_when_disabled():
    conn = get_connection(":memory:")
    skill_repo = SkillRepository(conn)
    agent_repo = AgentRepository(conn)
    skill_repo.save("executor", "coding", "Always validate inputs.", "t0")

    registry = AgentRegistry(agent_repo=agent_repo)
    registry.seed_defaults()

    class FakeLLM:
        def count_tokens(self, text): return 0

    cfg = CrabShrimpConfig(skill_injection_enabled=False)
    factory = AgentFactory(llm_client=FakeLLM(), config=cfg, skill_repo=skill_repo)
    profiles = registry.list_by_role(RoleType.executor)
    agent = factory.create(profiles[0], task_category="coding")
    assert "Always validate inputs." not in agent.profile.system_prompt
