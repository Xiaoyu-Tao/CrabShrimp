import uuid
from typing import TYPE_CHECKING, List, Optional
from crabshrimp.agents.base import BaseAgent
from crabshrimp.agents.factory import AgentFactory
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.communication.blackboard import AsyncBlackboard
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.coral_meeting.meeting import CoralMeeting
from crabshrimp.display.rich_panel import RichDisplay
from crabshrimp.llm.base import BaseLLMClient
from crabshrimp.models.agent_profile import ContextMode, RoleType
from crabshrimp.tidal_pool.human_gate import HumanGate
from crabshrimp.tidal_pool.resource_guard import ResourceExhausted, ResourceGuard
from crabshrimp.trace.collector import TraceCollector
from .classifier import TaskClassifier
from .planner import ExecutionPlanner, ExecutionStep

if TYPE_CHECKING:
    from crabshrimp.db.role_weight_repo import RoleWeightRepository


class DragonKing:
    def __init__(
        self,
        llm_client: BaseLLMClient,
        registry: AgentRegistry,
        factory: AgentFactory,
        coral_meeting: CoralMeeting,
        resource_guard: ResourceGuard,
        trace_collector: TraceCollector,
        blackboard: AsyncBlackboard,
        config: CrabShrimpConfig,
        role_weight_repo: Optional["RoleWeightRepository"] = None,
        human_gate: Optional[HumanGate] = None,
        display: Optional[RichDisplay] = None,
    ):
        self._llm = llm_client
        self._registry = registry
        self._factory = factory
        self._coral_meeting = coral_meeting
        self._guard = resource_guard
        self._trace = trace_collector
        self._blackboard = blackboard
        self._config = config
        self._role_weight_repo = role_weight_repo
        self._human_gate = human_gate or HumanGate(enabled=False)
        self._display = display
        self._classifier = TaskClassifier(llm_client)
        self._planner = ExecutionPlanner(llm_client)
        self._current_category = "general"

    async def run_task(self, task_id: str, task_description: str) -> dict:
        cfg = self._config
        d = self._display  # shorthand; may be None

        if d is None:
            print(f"\n[DragonKing] 🐉 Task started: {task_id}")
            print(f"[DragonKing] Task: {task_description}")
            print(
                f"[DragonKing] Config — coral_meeting={cfg.coral_meeting_enabled} "
                f"classify={cfg.classify_enabled} trace={cfg.trace_enabled} "
                f"resource_guard={cfg.resource_guard_enabled}\n"
            )

        # 1. 任务分类（可关闭）
        if cfg.classify_enabled:
            category = await self._classifier.classify(task_description)
        else:
            category = "general"
        self._current_category = category

        if d is not None:
            d.set_category(category)
            d.log(f"[dim]Category:[/dim] [cyan]{category}[/cyan]")
        else:
            print(f"[DragonKing] Category: {category}")

        # 2. 生成执行计划
        steps = await self._planner.plan(task_description, category)

        if d is not None:
            d.log(f"[dim]Plan:[/dim] {len(steps)} steps")
        else:
            print(f"[DragonKing] Plan: {len(steps)} steps\n")

        # ── HITL 检查点 1：执行计划审核 ────────────────────────
        if cfg.hitl_on_plan:
            if d is not None:
                d.hitl_pause("Plan review — awaiting human approval")
            self._human_gate.review_plan(steps)   # HumanAborted → 任务终止
            if d is not None:
                d.hitl_resume()

        # 3. 按步骤执行
        last_output = ""
        all_outputs = []
        stopped_early = False
        step_counter = 0

        for step in steps:
            # 资源守护：步数检查（可关闭）
            if cfg.resource_guard_enabled:
                try:
                    self._guard.check_and_consume_step()
                except ResourceExhausted as e:
                    if d is not None:
                        d.log(f"[red]🛑 Step limit reached — wrapping up[/red]")
                    else:
                        print(f"[TidalPool] 🛑 {e} — triggering graceful wrap-up...")
                    stopped_early = True
                    break

            step_counter += 1
            agent = self._get_best_agent(step.role, category)

            if d is not None:
                score = getattr(agent.profile, "contribution_score", 1.0)
                d.begin_step(
                    step_num=self._guard.steps_used,
                    description=step.description,
                    role=step.role.value,
                    agent_id=agent.agent_id,
                    score=score,
                )
            else:
                print(f"[Step {step.step_id}] {step.description} → {step.role.value}")

            # 上下文隔离：isolated 角色只看紧邻上一步输出，防锚定偏差
            if (
                cfg.context_isolation_enabled
                and agent.profile.context_mode == ContextMode.isolated
            ):
                task_context = {
                    "task_description": task_description,
                    "subtask": step.description,
                    "output_to_review": last_output,
                    "outputs_to_summarize": [],
                }
                if d is None:
                    print(f"  [Isolation] {agent.role} running in isolated context mode")
            else:
                task_context = {
                    "task_description": task_description,
                    "subtask": step.description,
                    "output_to_review": last_output,
                    "outputs_to_summarize": all_outputs,
                }

            result = await agent.act(task_context)
            last_output = result.get("output", "")
            all_outputs.append({"agent_id": agent.agent_id, "output": last_output})

            if d is not None:
                d.end_step(agent.agent_id, result.get("result", "success"))

            # ── HITL 检查点 3：Verifier 判定失败 ───────────────
            if (
                cfg.hitl_on_verify_fail
                and step.role == RoleType.verifier
                and result.get("result") == "failure"
            ):
                if d is not None:
                    d.hitl_pause("Verifier failure — awaiting human review")
                gate_result = self._human_gate.review_verify_fail(
                    result.get("reasoning", last_output)
                )
                if d is not None:
                    d.hitl_resume()
                if gate_result.decision == "edit" and gate_result.edited_content:
                    last_output = gate_result.edited_content
                    all_outputs[-1]["output"] = last_output
                    if d is not None:
                        d.log("[yellow]✏️  Verifier output revised by human[/yellow]")
                    else:
                        print("[HITL] ✏️  Verifier 输出已由人工修订")

            # 资源守护：Token 检查（可关闭）
            if cfg.resource_guard_enabled:
                tokens = self._llm.count_tokens(last_output)
                try:
                    self._guard.check_and_consume_tokens(tokens)
                except ResourceExhausted as e:
                    if d is not None:
                        d.update_tokens(self._guard.tokens_used)
                        d.log(f"[red]🛑 Token budget reached — wrapping up[/red]")
                    else:
                        print(f"[TidalPool] 🛑 {e} — triggering graceful wrap-up...")
                    self._trace.record_step(
                        agent_id=agent.agent_id,
                        input_text=step.description,
                        reasoning=result.get("reasoning", ""),
                        output=last_output,
                        interactions=[],
                        result=result.get("result", "success"),
                    )
                    await self._blackboard.set_state(f"step_{step.step_id}_output", last_output)
                    stopped_early = True
                    break
                if d is not None:
                    d.update_tokens(self._guard.tokens_used)

            self._trace.record_step(
                agent_id=agent.agent_id,
                input_text=step.description,
                reasoning=result.get("reasoning", ""),
                output=last_output,
                interactions=[],
                result=result.get("result", "success"),
            )

            # 关键节点：触发 Coral-Meeting（可关闭）
            if cfg.coral_meeting_enabled and step.is_critical_node:
                participants = self._get_meeting_participants(step.role, category)
                if d is not None:
                    d.begin_meeting(step.description, len(participants))
                else:
                    print(f"[CoralMeeting] 🪸 Critical node — convening meeting...")

                consensus, _winner = await self._coral_meeting.convene(
                    task_id=task_id,
                    step_id=str(step.step_id),
                    topic=step.description,
                    participants=participants,
                    context=last_output,
                    shared_outputs=all_outputs,
                )

                if d is not None:
                    d.end_meeting(consensus)

                # ── HITL 检查点 2：Coral-Meeting 共识审核 ──────
                if cfg.hitl_on_critical:
                    if d is not None:
                        d.hitl_pause("Coral-Meeting consensus — awaiting human review")
                    gate_result = self._human_gate.review_decision(
                        step.description, consensus
                    )
                    if d is not None:
                        d.hitl_resume()
                    if gate_result.decision == "edit" and gate_result.edited_content:
                        consensus = gate_result.edited_content
                        if d is not None:
                            d.log("[yellow]✏️  Consensus revised by human[/yellow]")
                        else:
                            print("[HITL] ✏️  会议共识已由人工修订")

                last_output = consensus
                all_outputs.append({"agent_id": "coral-meeting", "output": consensus})

                if cfg.resource_guard_enabled:
                    tokens = self._llm.count_tokens(consensus)
                    try:
                        self._guard.check_and_consume_tokens(tokens)
                    except ResourceExhausted as e:
                        if d is not None:
                            d.update_tokens(self._guard.tokens_used)
                            d.log(f"[red]🛑 Token budget reached — wrapping up[/red]")
                        else:
                            print(f"[TidalPool] 🛑 {e} — triggering graceful wrap-up...")
                        await self._blackboard.set_state(f"step_{step.step_id}_output", last_output)
                        stopped_early = True
                        break
                    if d is not None:
                        d.update_tokens(self._guard.tokens_used)

            await self._blackboard.set_state(f"step_{step.step_id}_output", last_output)

        # 优雅退出：资源耗尽时，用 Summarizer 汇总已有结果
        if stopped_early and all_outputs:
            if d is not None:
                d.log("[dim]📋 Summarizing partial results…[/dim]")
            else:
                print("[DragonKing] 📋 Summarizing partial results...")
            last_output = await self._wrapup(task_description, all_outputs, task_id, category)

        if d is not None:
            d.complete(stopped_early=stopped_early)
        else:
            status = "⚠️  Partial" if stopped_early else "✅"
            print(f"\n[DragonKing] {status} Task completed: {task_id}")

        return {
            "task_id": task_id,
            "category": category,
            "final_output": last_output,
            "stopped_early": stopped_early,
        }

    def _get_best_agent(self, role: RoleType, task_category: str = "general") -> BaseAgent:
        profiles = self._registry.list_by_role(role)
        if not profiles:
            raise RuntimeError(f"No agent found for role: {role}")
        return self._factory.create(profiles[0], task_category=task_category)

    def _get_meeting_participants(
        self, primary_role: RoleType, task_category: str = "general"
    ) -> List[BaseAgent]:
        seen_roles = set()
        candidate_roles = [primary_role, RoleType.critic, RoleType.verifier]
        agents = []
        threshold = self._config.bench_threshold
        for role in candidate_roles:
            if role in seen_roles:
                continue
            seen_roles.add(role)
            profiles = self._registry.list_by_role(role)
            for profile in profiles:
                # 拓扑筛选：低于 bench_threshold 胜率的 Agent 不参与会议
                if self._role_weight_repo is not None:
                    rate = self._role_weight_repo.win_rate(
                        task_category, role.value, profile.agent_id
                    )
                    if rate < threshold:
                        print(
                            f"  [Topology] {profile.agent_id} benched "
                            f"(win_rate={rate:.2f} < {threshold})"
                        )
                        continue
                agents.append(self._factory.create(profile, task_category=task_category))
                break  # 每个角色取一个 Agent
        return agents

    async def _wrapup(
        self, task_description: str, all_outputs: list, task_id: str, task_category: str = "general"
    ) -> str:
        summarizer = self._get_best_agent(RoleType.summarizer, task_category)
        result = await summarizer.act({
            "task_description": task_description,
            "subtask": "Summarize all partial results into a final answer.",
            "output_to_review": "",
            "outputs_to_summarize": all_outputs,
        })
        summary = result.get("output", "")
        self._trace.record_step(
            agent_id=summarizer.agent_id,
            input_text="[wrapup]",
            reasoning=result.get("reasoning", ""),
            output=summary,
            interactions=[],
            result="success",
        )
        return summary
