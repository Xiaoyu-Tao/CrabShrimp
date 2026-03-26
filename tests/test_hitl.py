"""
Human-in-the-Loop (HITL) 测试

覆盖：
- HumanGate disabled → 所有检查点直接放行（空操作）
- 用户输入 A → approve
- 用户输入 X → 抛出 HumanAborted
- 用户输入 E + 修订内容 → edit result
- 无效输入后重试
"""
import pytest
from unittest.mock import MagicMock

from crabshrimp.tidal_pool.human_gate import HumanAborted, HumanGate, HumanGateResult


# ── 辅助 ─────────────────────────────────────────────────────


def _gate(responses: list) -> HumanGate:
    """返回使用 mock 输入的 HumanGate（enabled=True）。"""
    it = iter(responses)
    return HumanGate(enabled=True, input_fn=lambda _: next(it))


def _fake_steps():
    step = MagicMock()
    step.step_id = 1
    step.role.value = "Executor"
    step.description = "Do something"
    step.is_critical_node = False
    return [step]


# ── disabled 时全部放行 ───────────────────────────────────────


def test_disabled_review_plan_is_noop():
    gate = HumanGate(enabled=False)
    result = gate.review_plan(_fake_steps())
    assert result.decision == "approve"


def test_disabled_review_decision_is_noop():
    gate = HumanGate(enabled=False)
    result = gate.review_decision("topic", "consensus")
    assert result.decision == "approve"


def test_disabled_review_verify_fail_is_noop():
    gate = HumanGate(enabled=False)
    result = gate.review_verify_fail("verifier reasoning")
    assert result.decision == "approve"


# ── 用户输入 A → approve ──────────────────────────────────────


def test_approve_plan():
    gate = _gate(["A"])
    result = gate.review_plan(_fake_steps())
    assert result.decision == "approve"


def test_approve_decision():
    gate = _gate(["A"])
    result = gate.review_decision("topic", "consensus text")
    assert result.decision == "approve"


def test_approve_verify_fail():
    gate = _gate(["A"])
    result = gate.review_verify_fail("failed reasoning")
    assert result.decision == "approve"


# ── 用户输入 X → HumanAborted ────────────────────────────────


def test_abort_plan():
    gate = _gate(["X"])
    with pytest.raises(HumanAborted):
        gate.review_plan(_fake_steps())


def test_abort_decision():
    gate = _gate(["X"])
    with pytest.raises(HumanAborted):
        gate.review_decision("topic", "consensus")


def test_abort_verify_fail():
    gate = _gate(["X"])
    with pytest.raises(HumanAborted):
        gate.review_verify_fail("reasoning")


# ── 用户输入 E → edit ─────────────────────────────────────────


def test_edit_decision():
    gate = _gate(["E", "My revised consensus", ""])
    result = gate.review_decision("topic", "original")
    assert result.decision == "edit"
    assert result.edited_content == "My revised consensus"


def test_edit_verify_fail():
    gate = _gate(["E", "Fixed output line 1", "Fixed output line 2", ""])
    result = gate.review_verify_fail("verifier said no")
    assert result.decision == "edit"
    assert "Fixed output line 1" in result.edited_content
    assert "Fixed output line 2" in result.edited_content


def test_edit_not_supported_for_plan():
    """plan review 不支持 E，输入 E 后提示无效，再输入 A。"""
    gate = _gate(["E", "A"])
    result = gate.review_plan(_fake_steps())
    assert result.decision == "approve"


# ── 无效输入后重试 ────────────────────────────────────────────


def test_invalid_input_retries_until_valid():
    gate = _gate(["Z", "Q", "A"])
    result = gate.review_plan(_fake_steps())
    assert result.decision == "approve"


# ── EOFError → HumanAborted ──────────────────────────────────


def test_eof_raises_human_aborted():
    def eof_input(_):
        raise EOFError

    gate = HumanGate(enabled=True, input_fn=eof_input)
    with pytest.raises(HumanAborted):
        gate.review_plan(_fake_steps())
