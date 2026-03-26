import os
from pydantic import BaseModel, Field


class CrabShrimpConfig(BaseModel):
    """虾兵蟹将运行时全局配置。所有机制开关和资源参数均在此集中管理。"""

    # ── LLM ──────────────────────────────────────────────────
    model: str = "claude-sonnet-4-6"
    api_base: str | None = None

    # ── 资源控制 ──────────────────────────────────────────────
    step_limit: int = 50
    token_budget: int = 100_000

    # ── 机制开关 ──────────────────────────────────────────────
    # 是否在关键节点触发 Coral-Meeting 多智能体集体审议
    coral_meeting_enabled: bool = True
    # 是否调用 LLM 进行任务分类（关闭后固定为 "general"）
    classify_enabled: bool = True
    # 是否将每步执行写入 JSONL Trace 文件
    trace_enabled: bool = True
    # 是否启用 Tidal-Pool 资源守护（关闭后无步数/Token 限制）
    resource_guard_enabled: bool = True

    # ── 隔离开关 ──────────────────────────────────────────────
    # 上下文隔离：isolated 角色只看到紧邻上一步输出，不看完整历史
    context_isolation_enabled: bool = True
    # 工作空间隔离：scoped 角色拥有独立临时目录
    workspace_isolation_enabled: bool = True
    # 执行环境隔离：subprocess 角色在隔离子进程中运行命令
    exec_isolation_enabled: bool = True

    # ── v0.3 演化开关 ─────────────────────────────────────────
    # 是否在任务结束后从 Trace 中提取 Skill 写入知识库
    skill_extraction_enabled: bool = True
    # 是否在 Agent 执行前将历史 Skill 注入 system prompt
    skill_injection_enabled: bool = True
    # Coral-Meeting 拓扑筛选阈值：低于此胜率的 Agent 不参与会议投票
    bench_threshold: float = 0.5

    # ── Human-in-the-Loop ────────────────────────────────────
    # 总开关：是否启用人在回路（默认关闭，不影响自动化流程）
    hitl_enabled: bool = False
    # 检查点 1：执行计划生成后，人工审核再执行
    hitl_on_plan: bool = True
    # 检查点 2：Coral-Meeting 共识后，人工审核再继续
    hitl_on_critical: bool = True
    # 检查点 3：Verifier 判定失败后，人工决定是否继续
    hitl_on_verify_fail: bool = True

    # ── v0.4 优化器 ───────────────────────────────────────────
    # 是否在任务结束后运行 Optimizer Agent（分析 Trace 改写低效 Prompt）
    optimizer_enabled: bool = False

    # ── 显示 ──────────────────────────────────────────────────
    # 是否启用 Rich 实时面板（终端可视化）
    display_enabled: bool = True

    # ── 路径 ──────────────────────────────────────────────────
    trace_dir: str = "./traces"
    db_path: str = "./crabshrimp.db"

    @classmethod
    def from_env(cls) -> "CrabShrimpConfig":
        """从环境变量读取配置，缺失项使用字段默认值。"""

        def _bool(key: str, default: bool) -> bool:
            val = os.getenv(key)
            if val is None:
                return default
            return val.lower() not in ("0", "false", "no", "off")

        return cls(
            model=os.getenv("CRABSHRIMP_MODEL", "claude-sonnet-4-6"),
            api_base=os.getenv("CRABSHRIMP_API_BASE") or None,
            step_limit=int(os.getenv("CRABSHRIMP_STEP_LIMIT", "50")),
            token_budget=int(os.getenv("CRABSHRIMP_TOKEN_BUDGET", "100000")),
            coral_meeting_enabled=_bool("CRABSHRIMP_CORAL_MEETING", True),
            classify_enabled=_bool("CRABSHRIMP_CLASSIFY", True),
            trace_enabled=_bool("CRABSHRIMP_TRACE", True),
            resource_guard_enabled=_bool("CRABSHRIMP_RESOURCE_GUARD", True),
            context_isolation_enabled=_bool("CRABSHRIMP_CONTEXT_ISOLATION", True),
            workspace_isolation_enabled=_bool("CRABSHRIMP_WORKSPACE_ISOLATION", True),
            exec_isolation_enabled=_bool("CRABSHRIMP_EXEC_ISOLATION", True),
            skill_extraction_enabled=_bool("CRABSHRIMP_SKILL_EXTRACTION", True),
            skill_injection_enabled=_bool("CRABSHRIMP_SKILL_INJECTION", True),
            bench_threshold=float(os.getenv("CRABSHRIMP_BENCH_THRESHOLD", "0.5")),
            hitl_enabled=_bool("CRABSHRIMP_HITL", False),
            hitl_on_plan=_bool("CRABSHRIMP_HITL_ON_PLAN", True),
            hitl_on_critical=_bool("CRABSHRIMP_HITL_ON_CRITICAL", True),
            hitl_on_verify_fail=_bool("CRABSHRIMP_HITL_ON_VERIFY_FAIL", True),
            optimizer_enabled=_bool("CRABSHRIMP_OPTIMIZER", False),
            display_enabled=_bool("CRABSHRIMP_DISPLAY", True),
            trace_dir=os.getenv("CRABSHRIMP_TRACE_DIR", "./traces"),
            db_path=os.getenv("CRABSHRIMP_DB_PATH", "./crabshrimp.db"),
        )
