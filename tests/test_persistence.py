"""
v0.2a 数据持久化测试
- AgentRepository: save / load / update_contribution
- TaskRepository: save / count
- MeetingRepository: save_outcome / wins_by_agent
- AgentRegistry: 从 DB 加载后 seed_defaults 不覆盖历史 contribution_score
"""
import sqlite3
import tempfile
import os

from crabshrimp.db.connection import get_connection
from crabshrimp.db.agent_repo import AgentRepository
from crabshrimp.db.task_repo import TaskRepository
from crabshrimp.db.meeting_repo import MeetingRepository
from crabshrimp.db.role_weight_repo import RoleWeightRepository
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.models.agent_profile import AgentProfile, RoleType, ContextMode, WorkspaceMode, ExecMode
from crabshrimp.models.trace import Interaction, TraceStep
from crabshrimp.tidal_pool.shell_molting import ShellMolting


# ── AgentRepository ──────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    return get_connection(":memory:")


def test_agent_repo_save_and_load():
    conn = _make_conn()
    repo = AgentRepository(conn)
    profile = AgentProfile(
        agent_id="critic-001",
        role=RoleType.critic,
        system_prompt="You are a Critic.",
        contribution_score=1.5,
        context_mode=ContextMode.isolated,
        workspace_mode=WorkspaceMode.none,
        exec_mode=ExecMode.local,
    )
    repo.save(profile)
    loaded = repo.load("critic-001")
    assert loaded is not None
    assert loaded.contribution_score == 1.5
    assert loaded.context_mode == ContextMode.isolated


def test_agent_repo_upsert_preserves_score():
    conn = _make_conn()
    repo = AgentRepository(conn)
    profile = AgentProfile(
        agent_id="critic-001", role=RoleType.critic,
        system_prompt="v1", contribution_score=1.8,
    )
    repo.save(profile)
    # 用新 prompt 再次 save
    profile2 = AgentProfile(
        agent_id="critic-001", role=RoleType.critic,
        system_prompt="v2", contribution_score=1.8,
    )
    repo.save(profile2)
    loaded = repo.load("critic-001")
    assert loaded.system_prompt == "v2"
    assert loaded.contribution_score == 1.8


def test_agent_repo_update_contribution():
    conn = _make_conn()
    repo = AgentRepository(conn)
    profile = AgentProfile(
        agent_id="executor-001", role=RoleType.executor, system_prompt="exec",
    )
    repo.save(profile)
    repo.update_contribution("executor-001", 1.3)
    loaded = repo.load("executor-001")
    assert abs(loaded.contribution_score - 1.3) < 1e-6


def test_agent_repo_load_all():
    conn = _make_conn()
    repo = AgentRepository(conn)
    for role in [RoleType.planner, RoleType.executor, RoleType.critic]:
        repo.save(AgentProfile(agent_id=f"{role.value.lower()}-001", role=role, system_prompt="x"))
    assert len(repo.load_all()) == 3


# ── TaskRepository ───────────────────────────────────────────

def test_task_repo_save_and_count():
    conn = _make_conn()
    repo = TaskRepository(conn)
    repo.save("task-1", "Test task", "analysis", False, 5, "./traces/task-1.jsonl")
    repo.save("task-2", "Test task 2", "code", True, 3, "./traces/task-2.jsonl")
    assert repo.count() == 2


# ── MeetingRepository ────────────────────────────────────────

def test_meeting_repo_save_and_wins():
    conn = _make_conn()
    repo = MeetingRepository(conn)
    repo.save_outcome("task-1", "step-3", "critic-001", "Review design")
    repo.save_outcome("task-1", "step-5", "critic-001", "Final check")
    repo.save_outcome("task-2", "step-2", "verifier-001", "Verify code")
    assert repo.wins_by_agent("critic-001") == 2
    assert repo.wins_by_agent("verifier-001") == 1


def test_meeting_repo_arbitrated_winner_is_none():
    conn = _make_conn()
    repo = MeetingRepository(conn)
    repo.save_outcome("task-1", "step-3", None, "Tied vote")
    assert repo.wins_by_agent("critic-001") == 0


def test_meeting_repo_get_outcomes_for_task():
    conn = _make_conn()
    repo = MeetingRepository(conn)
    repo.save_outcome("task-1", "step-3", "critic-001", "Review")
    repo.save_outcome("task-1", "step-4", None, "Tie")
    assert repo.get_outcomes_for_task("task-1") == [
        ("step-3", "critic-001"),
        ("step-4", None),
    ]


def test_role_weight_repo_normalizes_role_names():
    conn = _make_conn()
    repo = RoleWeightRepository(conn)
    repo.record_participation("analysis", "executor", "executor-001")
    assert repo.win_rate("analysis", "Executor", "executor-001") == 0.0


def test_shell_molting_updates_only_actual_meeting_participants():
    conn = _make_conn()
    registry = AgentRegistry(agent_repo=AgentRepository(conn))
    registry.seed_defaults()
    meeting_repo = MeetingRepository(conn)
    role_weight_repo = RoleWeightRepository(conn)

    meeting_repo.save_outcome("task-1", "meeting-step-1", "critic-001", "Review")
    steps = [
        TraceStep(
            step_id="executor-step-1",
            task_id="task-1",
            agent_id="executor-001",
            input="draft",
            reasoning="reasoning",
            output="executor-output",
            result="success",
        ),
        TraceStep(
            step_id="meeting-step-1",
            task_id="task-1",
            agent_id="coral-meeting",
            input="review",
            reasoning="{}",
            output="critic consensus",
            interactions=[
                Interaction(agent_id="critic-001", reaction="supplement", content="c"),
                Interaction(agent_id="verifier-001", reaction="supplement", content="v"),
            ],
            result="success",
        ),
    ]

    ShellMolting(registry, meeting_repo, role_weight_repo).evolve(
        "task-1", steps, stopped_early=False, task_category="analysis"
    )

    rows = sorted(role_weight_repo.get_all_for_category("analysis"))
    assert rows == [
        ("critic", "critic-001", 1.0),
        ("verifier", "verifier-001", 0.0),
    ]


# ── AgentRegistry + DB 集成 ──────────────────────────────────

def test_registry_preserves_contribution_score_across_runs():
    """模拟两次运行：第一次修改了 critic 的 score，第二次 seed_defaults 不应覆盖它。"""
    conn = _make_conn()
    repo = AgentRepository(conn)

    # 第一次运行：seed_defaults，然后修改 critic 的 score
    registry1 = AgentRegistry(agent_repo=repo)
    registry1.seed_defaults()
    registry1.update_contribution("critic-001", +0.5)  # score = 1.5

    # 第二次运行：重新加载
    registry2 = AgentRegistry(agent_repo=repo)  # 从 DB 加载 → critic score = 1.5
    registry2.seed_defaults()                    # critic-001 已存在，跳过

    critic = registry2.list_by_role(RoleType.critic)[0]
    assert abs(critic.contribution_score - 1.5) < 1e-6
