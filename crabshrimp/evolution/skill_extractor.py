"""
Skill 提取器（v0.3）

从单次任务 Trace 中提取可复用的推理技巧（Skill），写入 SkillRepository。
只提取「成功」步骤（result == "success"）中的 Executor / Planner / Summarizer 角色，
评估者（Critic / Verifier）和会议节点不纳入提取范围。

提取逻辑：
  - 对每个成功步骤，调用 LLM 用 100 字以内总结该步骤的核心推理技巧
  - 如果 LLM 返回空字符串或 "N/A"，跳过写库
  - 同一 (role, task_category) 已有 ≥ MAX_SKILLS_PER_SLOT 条记录时不再写入
"""
from typing import List

from crabshrimp.db.skill_repo import SkillRepository
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.trace import TraceStep

# 每个 (role, task_category) 槽最多保留的 Skill 数量
MAX_SKILLS_PER_SLOT = 10

# 只对这些角色提取 Skill（评估者排除）
_EXTRACTABLE_ROLES = {"planner", "executor", "summarizer"}

_SYSTEM_PROMPT = (
    "You are a skill extraction assistant for a multi-agent system. "
    "Your job is to distill reusable reasoning patterns from agent trace steps."
)

_EXTRACT_TEMPLATE = """\
The following is a single step from an AI agent's reasoning trace.

Role: {role}
Task category: {task_category}
Input: {input_text}
Reasoning: {reasoning}
Output: {output}

In at most 2 sentences (under 100 words), describe the core reusable reasoning skill \
demonstrated in this step. If no generalizable skill is present, respond with exactly: N/A
"""


class SkillExtractor:
    """
    异步 Skill 提取器。在每次任务结束后调用 extract_and_save()。
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        skill_repo: SkillRepository,
    ):
        self._llm = llm_client
        self._repo = skill_repo

    async def extract_and_save(
        self,
        task_id: str,
        task_category: str,
        steps: List[TraceStep],
    ) -> int:
        """
        遍历 trace steps，提取 Skill 并写库。
        返回本次成功写入的 Skill 数量。
        """
        saved = 0
        for step in steps:
            role = self._infer_role(step.agent_id)
            if role not in _EXTRACTABLE_ROLES:
                continue
            if step.result != "success":
                continue

            # 同一槽已满则跳过
            count = self._repo.count_by_role_category(role, task_category)
            if count >= MAX_SKILLS_PER_SLOT:
                continue

            skill_content = await self._call_llm(role, task_category, step)
            if not skill_content or skill_content.strip().upper() == "N/A":
                continue

            self._repo.save(
                role=role,
                task_category=task_category,
                content=skill_content.strip(),
                source_task_id=task_id,
            )
            saved += 1

        if saved:
            print(f"\n[SkillExtractor] 💡 Extracted {saved} skill(s) from task {task_id}")
        return saved

    async def _call_llm(
        self, role: str, task_category: str, step: TraceStep
    ) -> str:
        prompt = _EXTRACT_TEMPLATE.format(
            role=role,
            task_category=task_category,
            input_text=step.input[:500],
            reasoning=(step.reasoning or "")[:800],
            output=(step.output or "")[:500],
        )
        try:
            return await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"[SkillExtractor] LLM error for {step.agent_id}: {e}")
            return ""

    @staticmethod
    def _infer_role(agent_id: str) -> str:
        """从 agent_id 前缀推断角色名（e.g. 'executor-001' → 'executor'）。"""
        return agent_id.split("-")[0]
