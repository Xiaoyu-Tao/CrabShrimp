"""Unit tests for v0.4 Optimizer Agent and OptimizationRepository."""
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crabshrimp.db.connection import get_connection
from crabshrimp.db.optimization_repo import OptimizationRepository
from crabshrimp.models.trace import TraceStep
from crabshrimp.optimizer.optimizer_agent import OptimizerAgent

# Default threshold kept here for test legibility (mirrors CrabShrimpConfig default)
DELTA_THRESHOLD = -0.05


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    conn = get_connection(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def opt_repo(conn):
    return OptimizationRepository(conn)


def make_step(agent_id: str, result: str = "success", input_text: str = "do x", output: str = "done") -> TraceStep:
    import uuid
    return TraceStep(
        step_id=str(uuid.uuid4()),
        task_id="task-test",
        agent_id=agent_id,
        input=input_text,
        reasoning="",
        output=output,
        interactions=[],
        result=result,
    )


# ── OptimizationRepository tests ──────────────────────────────────────────────

class TestOptimizationRepository:
    def test_save_and_retrieve(self, opt_repo):
        opt_repo.save("executor", "code", "Be more specific about edge cases.", "task-1")
        pairs = opt_repo.get_top("executor", "code", limit=1)
        assert len(pairs) == 1
        assert "edge cases" in pairs[0][1]

    def test_get_top_empty(self, opt_repo):
        assert opt_repo.get_top("planner", "general") == []

    def test_increment_usage(self, opt_repo):
        opt_id = opt_repo.save("executor", "code", "Some patch.", "task-1")
        opt_repo.increment_usage(opt_id)
        pairs = opt_repo.get_top("executor", "code")
        assert len(pairs) == 1  # still there

    def test_count_by_role_category(self, opt_repo):
        opt_repo.save("executor", "code", "patch 1", "task-1")
        opt_repo.save("executor", "code", "patch 2", "task-2")
        assert opt_repo.count_by_role_category("executor", "code") == 2
        assert opt_repo.count_by_role_category("planner", "code") == 0

    def test_max_per_slot_not_enforced_by_repo(self, opt_repo):
        # The repo itself doesn't enforce the cap — the optimizer does.
        for i in range(OptimizationRepository.MAX_PER_SLOT + 2):
            opt_repo.save("executor", "code", f"patch {i}", "task-x")
        assert opt_repo.count_by_role_category("executor", "code") == OptimizationRepository.MAX_PER_SLOT + 2

    def test_get_top_ordered_by_usage(self, opt_repo):
        id1 = opt_repo.save("executor", "code", "less used", "task-1")
        id2 = opt_repo.save("executor", "code", "more used", "task-2")
        opt_repo.increment_usage(id2)
        opt_repo.increment_usage(id2)
        pairs = opt_repo.get_top("executor", "code", limit=1)
        assert pairs[0][1] == "more used"


# ── OptimizerAgent tests ───────────────────────────────────────────────────────

class TestOptimizerAgent:
    def _make_optimizer(self, opt_repo, llm_response="Use structured output."):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=llm_response)

        mock_agent_repo = MagicMock()
        mock_profile = MagicMock()
        mock_profile.system_prompt = "You are an executor."
        mock_agent_repo.list_by_role.return_value = [mock_profile]

        return OptimizerAgent(mock_llm, mock_agent_repo, opt_repo)

    @pytest.mark.asyncio
    async def test_no_bad_agents_no_save(self, opt_repo):
        optimizer = self._make_optimizer(opt_repo)
        steps = [make_step("executor-001", result="success")]
        saved = await optimizer.optimize("task-1", "code", steps, {"executor-001": 0.0})
        assert saved == 0
        assert opt_repo.count_by_role_category("executor", "code") == 0

    @pytest.mark.asyncio
    async def test_negative_delta_triggers_optimization(self, opt_repo):
        optimizer = self._make_optimizer(opt_repo, "Add explicit validation steps.")
        steps = [make_step("executor-001", result="success")]
        saved = await optimizer.optimize(
            "task-1", "code", steps, {"executor-001": DELTA_THRESHOLD - 0.01}
        )
        assert saved == 1
        pairs = opt_repo.get_top("executor", "code")
        assert "validation" in pairs[0][1]

    @pytest.mark.asyncio
    async def test_failure_result_triggers_optimization(self, opt_repo):
        optimizer = self._make_optimizer(opt_repo, "Break task into smaller parts.")
        steps = [make_step("planner-001", result="failure")]
        saved = await optimizer.optimize("task-1", "analysis", steps, {})
        assert saved == 1

    @pytest.mark.asyncio
    async def test_na_response_not_saved(self, opt_repo):
        optimizer = self._make_optimizer(opt_repo, "N/A")
        steps = [make_step("executor-001", result="failure")]
        saved = await optimizer.optimize("task-1", "code", steps, {})
        assert saved == 0

    @pytest.mark.asyncio
    async def test_evaluator_roles_excluded(self, opt_repo):
        optimizer = self._make_optimizer(opt_repo, "Some patch.")
        steps = [
            make_step("critic-001", result="failure"),
            make_step("verifier-001", result="failure"),
        ]
        deltas = {"critic-001": -0.20, "verifier-001": -0.20}
        saved = await optimizer.optimize("task-1", "code", steps, deltas)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_slot_cap_respected(self, opt_repo):
        # Pre-fill the slot to the cap
        for i in range(OptimizationRepository.MAX_PER_SLOT):
            opt_repo.save("executor", "code", f"patch {i}", "task-old")

        optimizer = self._make_optimizer(opt_repo, "New patch.")
        steps = [make_step("executor-001", result="failure")]
        saved = await optimizer.optimize("task-new", "code", steps, {})
        assert saved == 0  # cap reached, nothing new written

    @pytest.mark.asyncio
    async def test_llm_error_skips_gracefully(self, opt_repo):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_agent_repo = MagicMock()
        mock_profile = MagicMock()
        mock_profile.system_prompt = "You are an executor."
        mock_agent_repo.list_by_role.return_value = [mock_profile]

        optimizer = OptimizerAgent(mock_llm, mock_agent_repo, opt_repo)
        steps = [make_step("executor-001", result="failure")]
        saved = await optimizer.optimize("task-1", "code", steps, {})
        assert saved == 0  # error swallowed, no crash
