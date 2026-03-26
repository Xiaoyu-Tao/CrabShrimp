import asyncio
import uuid
from pathlib import Path

from crabshrimp.agents.factory import AgentFactory
from crabshrimp.agents.registry import AgentRegistry
from crabshrimp.communication.blackboard import AsyncBlackboard
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.coral_meeting.meeting import CoralMeeting
from crabshrimp.db import AgentRepository, MeetingRepository, OptimizationRepository, RoleWeightRepository, SkillRepository, TaskRepository, get_connection
from crabshrimp.display.rich_panel import RichDisplay
from crabshrimp.dragon_king.orchestrator import DragonKing
from crabshrimp.evolution.skill_extractor import SkillExtractor
from crabshrimp.optimizer.optimizer_agent import OptimizerAgent
from crabshrimp.tidal_pool.shell_molting import ShellMolting
from crabshrimp.llm.litellm_client import LiteLLMClient
from crabshrimp.tidal_pool.human_gate import HumanAborted, HumanGate
from crabshrimp.tidal_pool.resource_guard import ResourceExhausted, ResourceGuard
from crabshrimp.tidal_pool.workspace import WorkspaceManager
from crabshrimp.trace.collector import TraceCollector
from crabshrimp.trace.writer import NullTraceWriter, TraceWriter


class TaskRunner:
    def __init__(self, config: CrabShrimpConfig):
        self._config = config

    def run(self, task_description: str) -> dict:
        return asyncio.run(self._run_async(task_description))

    async def _run_async(self, task_description: str) -> dict:
        cfg = self._config
        task_id = str(uuid.uuid4())[:8]
        trace_path = Path(cfg.trace_dir) / f"task_{task_id}.jsonl" if cfg.trace_enabled else None

        # ── DB 初始化 ───────────────────────────────────────────
        conn = get_connection(cfg.db_path)
        agent_repo = AgentRepository(conn)
        task_repo = TaskRepository(conn)
        meeting_repo = MeetingRepository(conn)
        skill_repo = SkillRepository(conn)
        role_weight_repo = RoleWeightRepository(conn)
        optimization_repo = OptimizationRepository(conn)

        # ── 组件装配 ────────────────────────────────────────────
        llm_client = LiteLLMClient(model=cfg.model, api_base=cfg.api_base)

        registry = AgentRegistry(agent_repo=agent_repo)
        registry.seed_defaults()   # 已在 DB 的角色保留历史 contribution_score

        workspace_manager = WorkspaceManager(task_id=task_id)
        factory = AgentFactory(
            llm_client=llm_client,
            workspace_manager=workspace_manager,
            config=cfg,
            skill_repo=skill_repo,
            optimization_repo=optimization_repo,
        )
        guard = ResourceGuard(step_limit=cfg.step_limit, token_budget=cfg.token_budget)

        result: dict = {}
        steps_count = 0
        collector: TraceCollector | None = None

        display = RichDisplay(
            task=task_description,
            step_limit=cfg.step_limit,
            token_budget=cfg.token_budget,
            enabled=cfg.display_enabled,
        )

        try:
            writer = TraceWriter(str(trace_path)) if trace_path is not None else NullTraceWriter()
            with writer, display:
                collector = TraceCollector(
                    task_id=task_id,
                    writer=writer,
                    enabled=cfg.trace_enabled,
                )
                blackboard = AsyncBlackboard()
                coral_meeting = CoralMeeting(
                    llm_client=llm_client,
                    trace_collector=collector,
                    meeting_repo=meeting_repo,
                )
                human_gate = HumanGate(enabled=cfg.hitl_enabled)
                dragon_king = DragonKing(
                    llm_client=llm_client,
                    registry=registry,
                    factory=factory,
                    coral_meeting=coral_meeting,
                    resource_guard=guard,
                    trace_collector=collector,
                    blackboard=blackboard,
                    config=cfg,
                    role_weight_repo=role_weight_repo,
                    human_gate=human_gate,
                    display=display if cfg.display_enabled else None,
                )

                try:
                    result = await dragon_king.run_task(task_id, task_description)
                except ResourceExhausted as e:
                    print(f"\n[Runner] Task stopped: {e}")
                    result = {
                        "task_id": task_id,
                        "final_output": "Task stopped due to resource limit.",
                        "stopped_early": True,
                        "category": "general",
                        "error": str(e),
                    }
                except HumanAborted as e:
                    print(f"\n[Runner] Task aborted by human: {e}")
                    result = {
                        "task_id": task_id,
                        "final_output": f"任务已由人工终止：{e}",
                        "stopped_early": True,
                        "category": "general",
                        "error": str(e),
                    }
                finally:
                    steps_count = len(collector.get_all_steps())
                    if workspace_manager.list_workspaces():
                        workspace_manager.cleanup()

            # ── Shell-Molting：分析信号，更新 contribution_score ───
            shell_molting = ShellMolting(
                registry=registry,
                meeting_repo=meeting_repo,
                role_weight_repo=role_weight_repo,
            )
            evolution_deltas = shell_molting.evolve(
                task_id=task_id,
                steps=collector.get_all_steps(),
                stopped_early=result.get("stopped_early", False),
                task_category=result.get("category", "general"),
            )
            result["evolution_deltas"] = evolution_deltas

            # ── Prompt 优化（v0.4）───────────────────────────────
            if cfg.optimizer_enabled:
                optimizer = OptimizerAgent(
                    llm_client=llm_client,
                    agent_repo=agent_repo,
                    optimization_repo=optimization_repo,
                )
                await optimizer.optimize(
                    task_id=task_id,
                    task_category=result.get("category", "general"),
                    steps=collector.get_all_steps(),
                    evolution_deltas=evolution_deltas,
                )

            # ── Skill 提取（v0.3）────────────────────────────────
            if cfg.skill_extraction_enabled:
                skill_extractor = SkillExtractor(llm_client=llm_client, skill_repo=skill_repo)
                await skill_extractor.extract_and_save(
                    task_id=task_id,
                    task_category=result.get("category", "general"),
                    steps=collector.get_all_steps(),
                )

            # ── 持久化任务摘要 ──────────────────────────────────────
            task_repo.save(
                task_id=task_id,
                description=task_description,
                category=result.get("category", "general"),
                stopped_early=result.get("stopped_early", False),
                steps_count=steps_count,
                trace_path=str(trace_path) if trace_path is not None else "",
            )
        finally:
            conn.close()

        if trace_path is not None:
            print(f"\n[Runner] Trace saved → {trace_path} ({steps_count} steps)")
            result["trace_path"] = str(trace_path)
        else:
            print(f"\n[Runner] Trace disabled. Steps executed: {steps_count}")
        result["steps_count"] = steps_count
        return result
