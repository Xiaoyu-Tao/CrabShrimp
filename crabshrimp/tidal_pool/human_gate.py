"""
Human-in-the-Loop（HITL）守门机制

在关键检查点暂停执行，等待人工审核与确认。支持三种检查点：
  review_plan         — 执行计划生成后，人工确认再开始
  review_decision     — Coral-Meeting 达成共识后，人工审核后再继续
  review_verify_fail  — Verifier 判定失败后，人工决定是否继续

disabled 时所有方法均为空操作（直接返回 approve），不影响正常执行流程。
input_fn 参数允许测试时注入 mock 输入，默认使用 Python 内置 input()。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional


class HumanAborted(Exception):
    """人工干预终止任务。"""


@dataclass
class HumanGateResult:
    decision: Literal["approve", "edit"]
    edited_content: str = ""


_SEP = "─" * 60


class HumanGate:
    def __init__(
        self,
        enabled: bool = False,
        input_fn: Optional[Callable[[str], str]] = None,
    ):
        self.enabled = enabled
        self._input = input_fn or input

    # ── 检查点 1：执行计划审核 ──────────────────────────────────
    def review_plan(self, steps: list) -> HumanGateResult:
        """展示执行计划，人工批准或终止。"""
        if not self.enabled:
            return HumanGateResult(decision="approve")

        print(f"\n{_SEP}")
        print("[HITL] 📋 执行计划待审核，请确认后再开始")
        print(_SEP)
        for s in steps:
            critical = " ★ 关键节点" if s.is_critical_node else ""
            print(f"  Step {s.step_id}  [{s.role.value}]  {s.description}{critical}")
        print(_SEP)
        print("  [A] 批准，开始执行")
        print("  [X] 终止任务")

        return self._prompt(supports_edit=False)

    # ── 检查点 2：关键决策审核（Coral-Meeting 共识后）──────────
    def review_decision(self, topic: str, consensus: str) -> HumanGateResult:
        """展示 Coral-Meeting 共识，人工批准、修改或终止。"""
        if not self.enabled:
            return HumanGateResult(decision="approve")

        print(f"\n{_SEP}")
        print("[HITL] 🪸 Coral-Meeting 共识待审核")
        print(f"议题：{topic}")
        print(_SEP)
        print(consensus[:1000] + ("..." if len(consensus) > 1000 else ""))
        print(_SEP)
        print("  [A] 批准共识，继续执行")
        print("  [E] 修改共识内容（输入新内容后按空行确认）")
        print("  [X] 终止任务")

        return self._prompt(supports_edit=True)

    # ── 检查点 3：Verifier 判定失败后 ──────────────────────────
    def review_verify_fail(self, reasoning: str) -> HumanGateResult:
        """Verifier 判定失败，人工决定是否强制继续或提供修订内容。"""
        if not self.enabled:
            return HumanGateResult(decision="approve")

        print(f"\n{_SEP}")
        print("[HITL] ⚠️  Verifier 判定失败，等待人工决策")
        print(_SEP)
        print(reasoning[:800] + ("..." if len(reasoning) > 800 else ""))
        print(_SEP)
        print("  [A] 忽略验证失败，继续执行")
        print("  [E] 提供修订内容（替换当前步骤输出，输入后按空行确认）")
        print("  [X] 终止任务")

        return self._prompt(supports_edit=True)

    # ── 内部：统一输入处理 ──────────────────────────────────────
    def _prompt(self, supports_edit: bool) -> HumanGateResult:
        hint = "A / E / X" if supports_edit else "A / X"
        while True:
            try:
                choice = self._input(f"\n请选择 [{hint}]: ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                raise HumanAborted("用户中断（Ctrl+C / EOF）")

            if choice == "A":
                return HumanGateResult(decision="approve")

            if choice == "E" and supports_edit:
                print("请输入修订内容（输入完成后按空行确认）：")
                lines: List[str] = []
                try:
                    while True:
                        line = self._input("")
                        if line == "":
                            break
                        lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    raise HumanAborted("用户中断（Ctrl+C / EOF）")
                content = "\n".join(lines).strip()
                return HumanGateResult(decision="edit", edited_content=content)

            if choice == "X":
                raise HumanAborted("用户终止任务")

            opts = "A、E 或 X" if supports_edit else "A 或 X"
            print(f"  无效选项，请输入 {opts}")
