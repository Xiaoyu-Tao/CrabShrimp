import json
import re
from dataclasses import dataclass
from typing import List
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.agent_profile import RoleType
from .classifier import TaskCategory

_PLAN_PROMPT = """You are an execution planner for a multi-agent system.
Given a task, produce a JSON execution plan. Each step must have:
- step_id: integer
- description: what to do in this step
- role: one of Planner, Executor, Critic, Verifier, Summarizer
- is_critical_node: true if this step requires multi-agent deliberation, false otherwise

Rules:
- Mark steps as critical if they involve key decisions, risk, or significant uncertainty.
- The final step should always be Summarizer.
- Output ONLY valid JSON, no markdown fences.

Example output:
[
  {"step_id": 1, "description": "Analyze requirements", "role": "Planner", "is_critical_node": false},
  {"step_id": 2, "description": "Implement solution", "role": "Executor", "is_critical_node": false},
  {"step_id": 3, "description": "Review implementation", "role": "Critic", "is_critical_node": true},
  {"step_id": 4, "description": "Summarize results", "role": "Summarizer", "is_critical_node": false}
]"""


@dataclass
class ExecutionStep:
    step_id: int
    description: str
    role: RoleType
    is_critical_node: bool


class ExecutionPlanner:
    def __init__(self, llm_client: BaseLLMClient):
        self._llm = llm_client

    async def plan(
        self,
        task_description: str,
        task_category: TaskCategory,
    ) -> List[ExecutionStep]:
        prompt = f"Task category: {task_category}\nTask: {task_description}"
        messages = [{"role": "user", "content": prompt}]
        raw = await self._llm.complete(messages, system_prompt=_PLAN_PROMPT)

        # 剥去 LLM 有时返回的 markdown fence（```json ... ```）
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            steps_data = json.loads(cleaned)
        except json.JSONDecodeError:
            # LLM 返回格式异常时，退回到最简单的两步计划
            steps_data = [
                {"step_id": 1, "description": task_description, "role": "Executor", "is_critical_node": False},
                {"step_id": 2, "description": "Summarize results", "role": "Summarizer", "is_critical_node": False},
            ]

        steps = []
        for i, s in enumerate(steps_data):
            try:
                role = RoleType(s.get("role", "Executor"))
            except (ValueError, KeyError, TypeError):
                role = RoleType.executor
            steps.append(
                ExecutionStep(
                    step_id=s.get("step_id", i + 1),
                    description=s.get("description", f"Step {i + 1}"),
                    role=role,
                    is_critical_node=s.get("is_critical_node", False),
                )
            )
        return steps
