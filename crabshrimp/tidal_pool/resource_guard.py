class ResourceExhausted(Exception):
    def __init__(self, resource_type: str, limit: int, used: int):
        self.resource_type = resource_type
        self.limit = limit
        self.used = used
        super().__init__(
            f"[TidalPool] {resource_type} exhausted: used={used}, limit={limit}"
        )


class ResourceGuard:
    def __init__(self, step_limit: int = 50, token_budget: int = 100_000):
        self._step_limit = step_limit
        self._token_budget = token_budget
        self._steps_used = 0
        self._tokens_used = 0

    def check_and_consume_step(self) -> None:
        self._steps_used += 1
        if self._steps_used > self._step_limit:
            raise ResourceExhausted("steps", self._step_limit, self._steps_used)
        # 只在首次达到 80% 时警告（避免重复打印）
        warn_at = int(self._step_limit * 0.8)
        if self._steps_used == warn_at:
            print(f"[TidalPool] ⚠️  Step warning: {self._steps_used}/{self._step_limit}")

    def check_and_consume_tokens(self, tokens: int) -> None:
        self._tokens_used += tokens
        if self._tokens_used > self._token_budget:
            raise ResourceExhausted("tokens", self._token_budget, self._tokens_used)
        warn_at = int(self._token_budget * 0.8)
        if self._tokens_used >= warn_at and (self._tokens_used - tokens) < warn_at:
            print(f"[TidalPool] ⚠️  Token warning: {self._tokens_used}/{self._token_budget}")

    @property
    def remaining_steps(self) -> int:
        return max(0, self._step_limit - self._steps_used)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self._token_budget - self._tokens_used)
