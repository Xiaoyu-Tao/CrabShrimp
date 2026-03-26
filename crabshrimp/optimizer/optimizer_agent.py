"""
Optimizer Agent（v0.4）

任务结束后，分析 Trace 信号和 evolution_deltas，找出表现较差的角色，
调用 LLM 生成针对性的 system prompt 改进建议，写入 prompt_optimizations 表。
下次同类任务创建同角色 Agent 时，会从该表注入建议（类似 Skill 注入机制）。

触发条件（任一满足即分析）：
- evolution_deltas 中某 agent_id 的 delta < DELTA_THRESHOLD
- trace 中某步骤 result == "failure"（且角色不是评估者）

每个 (role, task_category) 槽最多 MAX_PER_SLOT 条，防止过拟合。
"""
from __future__ import annotations

from typing import Dict, List

from crabshrimp.db.agent_repo import AgentRepository
from crabshrimp.db.optimization_repo import OptimizationRepository
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.trace import TraceStep

# 负向 delta 超过此阈值才触发优化分析
DELTA_THRESHOLD = -0.05

_SYSTEM_PROMPT = (
    "You are a prompt optimization specialist for a multi-agent AI system. "
    "Your job is to analyze agent underperformance and suggest concise, actionable "
    "improvements to the agent's system prompt."
)

_OPTIMIZE_TEMPLATE = """\
You are optimizing the system prompt for a role in a multi-agent collaboration framework.

Role: {role}
Task category: {task_category}

Current system prompt:
---
{system_prompt}
---

The agent underperformed in the following step(s) during the last task:

{bad_steps}

In 2-3 sentences (under 150 words), suggest a specific addition or modification to the \
system prompt that addresses the observed weakness. Write only the suggested text to add \
(not the full prompt). Focus on concrete behavioral instructions.
If no meaningful improvement can be identified, respond with exactly: N/A
"""


class OptimizerAgent:
    """
    分析失败 trace 步骤，为低分 Agent 角色生成 prompt 改进建议。

    用法::

        optimizer = OptimizerAgent(llm_client, agent_repo, optimization_repo)
        count = await optimizer.optimize(
            task_id=task_id,
            task_category="code",
            steps=collector.get_all_steps(),
            evolution_deltas={"executor-001": -0.10, "planner-001": 0.0},
        )
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        agent_repo: AgentRepository,
        optimization_repo: OptimizationRepository,
    ) -> None:
        self._llm = llm_client
        self._agent_repo = agent_repo
        self._opt_repo = optimization_repo

    async def optimize(
        self,
        task_id: str,
        task_category: str,
        steps: List[TraceStep],
        evolution_deltas: Dict[str, float],
    ) -> int:
        """
        分析 trace，为表现差的角色生成并存储 prompt 优化建议。
        返回成功写入的条数。
        """
        # 找出需要优化的角色集合
        roles_to_optimize = self._collect_bad_roles(steps, evolution_deltas)
        if not roles_to_optimize:
            return 0

        saved = 0
        for role in roles_to_optimize:
            # 槽已满则跳过
            if self._opt_repo.count_by_role_category(role, task_category) >= OptimizationRepository.MAX_PER_SLOT:
                continue

            # 获取该角色的当前 system prompt（取第一个匹配的 profile）
            system_prompt = self._get_system_prompt(role)
            if not system_prompt:
                continue

            # 收集该角色的问题步骤
            bad_steps_text = self._format_bad_steps(role, steps, evolution_deltas)

            patch = await self._call_llm(role, task_category, system_prompt, bad_steps_text)
            if not patch or patch.strip().upper() == "N/A":
                continue

            self._opt_repo.save(
                role=role,
                task_category=task_category,
                patch=patch.strip(),
                source_task_id=task_id,
            )
            saved += 1

        if saved:
            print(f"\n[Optimizer] 🔧 Generated {saved} prompt optimization(s) for task {task_id}")
        return saved

    # ── Internal helpers ────────────────────────────────────────────────────

    def _collect_bad_roles(
        self, steps: List[TraceStep], evolution_deltas: Dict[str, float]
    ) -> List[str]:
        """返回需要优化的角色名列表（去重）。"""
        bad_roles: set[str] = set()

        # 1. evolution_deltas 中 delta 超过阈值的 agent
        for agent_id, delta in evolution_deltas.items():
            if delta < DELTA_THRESHOLD:
                role = self._infer_role(agent_id)
                if role not in ("critic", "verifier", "coral-meeting"):
                    bad_roles.add(role)

        # 2. trace 中 result == "failure" 的非评估步骤
        for step in steps:
            if step.result == "failure":
                role = self._infer_role(step.agent_id)
                if role not in ("critic", "verifier", "coral-meeting"):
                    bad_roles.add(role)

        return sorted(bad_roles)

    def _get_system_prompt(self, role: str) -> str:
        """从 agent_profiles 取该角色的当前 system prompt。"""
        profiles = self._agent_repo.list_by_role(role)
        if not profiles:
            return ""
        return profiles[0].system_prompt

    def _format_bad_steps(
        self, role: str, steps: List[TraceStep], evolution_deltas: Dict[str, float]
    ) -> str:
        """把该角色的问题步骤格式化为文本。"""
        lines: List[str] = []
        for step in steps:
            if self._infer_role(step.agent_id) != role:
                continue
            delta = evolution_deltas.get(step.agent_id, 0.0)
            if step.result == "failure" or delta < DELTA_THRESHOLD:
                lines.append(
                    f"Input: {step.input[:300]}\n"
                    f"Output: {(step.output or '')[:300]}\n"
                    f"Result: {step.result}  |  Score delta: {delta:+.2f}"
                )
        return "\n\n".join(lines) if lines else "(no specific failed steps recorded)"

    async def _call_llm(
        self, role: str, task_category: str, system_prompt: str, bad_steps_text: str
    ) -> str:
        prompt = _OPTIMIZE_TEMPLATE.format(
            role=role,
            task_category=task_category,
            system_prompt=system_prompt[:1200],
            bad_steps=bad_steps_text,
        )
        try:
            return await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"[Optimizer] LLM error for role={role}: {e}")
            return ""

    @staticmethod
    def _infer_role(agent_id: str) -> str:
        return agent_id.split("-")[0]
