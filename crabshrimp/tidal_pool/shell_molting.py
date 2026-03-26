"""
Shell-Molting 演化引擎（v0.2b）

跨任务分析 Trace 信号，自动更新 Agent 的 contribution_score。
contribution_score 影响 Coral-Meeting 投票权重，并为 v0.3 的 Skill 提取提供优先级依据。

奖惩规则（v0.2b）：
  +0.10  Coral-Meeting 中立场被采纳（winner）
  -0.15  Verifier 判定 failure → 归因至最近上游非评估 Agent
  -0.10  Critic 判定 rejected  → 归因至最近上游非评估 Agent
  -0.05  任务 stopped_early   → 全体参与 Agent（轻惩）
"""
from typing import Dict, List, Optional

from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.db.meeting_repo import MeetingRepository
from crabshrimp.db.role_weight_repo import RoleWeightRepository
from crabshrimp.models.trace import TraceStep

# 不参与归因的 Agent 前缀（评估者 + 会议节点）
# 使用前缀而非精确 ID，兼容 verifier-002、critic-002 等多实例场景
_EVALUATOR_PREFIXES = ("verifier", "critic", "coral-meeting")


def _is_evaluator(agent_id: str) -> bool:
    return any(agent_id.startswith(p) for p in _EVALUATOR_PREFIXES)

# 奖惩幅度
_REWARD_MEETING_WIN  = +0.10
_PUNISH_VERIFY_FAIL  = -0.15
_PUNISH_CRITIC_REJECT = -0.10
_PUNISH_STOPPED_EARLY = -0.05


class ShellMolting:
    """
    任务结束后调用 evolve()，分析本次 Trace 并更新 contribution_score。
    所有变更通过 AgentRegistry.update_contribution() 同步写入 SQLite。
    """

    def __init__(
        self,
        registry: AgentRegistry,
        meeting_repo: MeetingRepository,
        role_weight_repo: Optional[RoleWeightRepository] = None,
    ):
        self._registry = registry
        self._meeting_repo = meeting_repo
        self._role_weight_repo = role_weight_repo

    def evolve(
        self,
        task_id: str,
        steps: List[TraceStep],
        stopped_early: bool,
        task_category: str = "general",
    ) -> Dict[str, float]:
        """
        分析信号，应用奖惩，返回各 Agent 本次的 delta 汇总。
        格式：{agent_id: delta}
        """
        deltas: Dict[str, float] = {}

        # ── 规则 1：Coral-Meeting winner 奖励 ─────────────────
        winners = self._meeting_repo.get_winners_for_task(task_id)
        for winner_id in winners:
            if winner_id:  # None = LLM 仲裁，无明确 winner
                deltas[winner_id] = deltas.get(winner_id, 0) + _REWARD_MEETING_WIN

        # ── 规则 2：Verifier failure → 归因惩罚 ───────────────
        for i, step in enumerate(steps):
            if step.agent_id.startswith("verifier") and step.result == "failure":
                upstream = _find_upstream(steps, i)
                if upstream:
                    deltas[upstream] = deltas.get(upstream, 0) + _PUNISH_VERIFY_FAIL

        # ── 规则 3：Critic rejected → 归因惩罚 ────────────────
        for i, step in enumerate(steps):
            if step.agent_id.startswith("critic") and step.result == "rejected":
                upstream = _find_upstream(steps, i)
                if upstream:
                    deltas[upstream] = deltas.get(upstream, 0) + _PUNISH_CRITIC_REJECT

        # ── 规则 4：stopped_early → 全员轻惩 ─────────────────
        if stopped_early:
            participants = {
                s.agent_id for s in steps
                if not _is_evaluator(s.agent_id)
            }
            for agent_id in participants:
                deltas[agent_id] = deltas.get(agent_id, 0) + _PUNISH_STOPPED_EARLY

        # ── 规则 5：更新 role_weights（拓扑调整依据）─────────
        if self._role_weight_repo is not None:
            winner_set = {w for w in self._meeting_repo.get_winners_for_task(task_id) if w}
            # 从 Trace 中读取每次会议的参与者（Interaction supplement 记录各方立场）
            for meeting_step in steps:
                if meeting_step.agent_id != "coral-meeting":
                    continue
                participants = {
                    interaction.agent_id
                    for interaction in meeting_step.interactions
                    if interaction.reaction == "supplement"
                }
                for agent_id in participants:
                    role = agent_id.split("-")[0]
                    if agent_id in winner_set:
                        self._role_weight_repo.record_win(task_category, role, agent_id)
                    else:
                        self._role_weight_repo.record_participation(
                            task_category, role, agent_id
                        )

        # ── 应用并打印变更 ────────────────────────────────────
        if deltas:
            print("\n[ShellMolting] 🐚 Evolution signals:")
            for agent_id, delta in sorted(deltas.items()):
                sign = "+" if delta >= 0 else ""
                print(f"  {agent_id:<20} {sign}{delta:+.2f}")
            for agent_id, delta in deltas.items():
                self._registry.update_contribution(agent_id, delta)
        else:
            print("\n[ShellMolting] No evolution signals this task.")

        return deltas


def _find_upstream(steps: List[TraceStep], evaluator_idx: int) -> Optional[str]:
    """
    从 evaluator_idx 往前找第一个非评估者的 Agent，作为归因目标。
    评估类 Agent（Verifier / Critic / CoralMeeting）不能归因给自己。
    """
    for i in range(evaluator_idx - 1, -1, -1):
        if not _is_evaluator(steps[i].agent_id):
            return steps[i].agent_id
    return None
