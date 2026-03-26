"""Phase 2 验证：ResourceGuard 资源控制。"""
import pytest
from crabshrimp.tidal_pool.resource_guard import ResourceGuard, ResourceExhausted


def test_step_limit():
    guard = ResourceGuard(step_limit=3, token_budget=10_000)
    guard.check_and_consume_step()
    guard.check_and_consume_step()
    guard.check_and_consume_step()
    with pytest.raises(ResourceExhausted) as exc_info:
        guard.check_and_consume_step()
    assert "steps" in str(exc_info.value)


def test_token_budget():
    guard = ResourceGuard(step_limit=50, token_budget=100)
    guard.check_and_consume_tokens(60)
    guard.check_and_consume_tokens(30)
    with pytest.raises(ResourceExhausted) as exc_info:
        guard.check_and_consume_tokens(20)
    assert "tokens" in str(exc_info.value)


def test_remaining():
    guard = ResourceGuard(step_limit=10, token_budget=1000)
    guard.check_and_consume_step()
    guard.check_and_consume_tokens(200)
    assert guard.remaining_steps == 9
    assert guard.remaining_tokens == 800
