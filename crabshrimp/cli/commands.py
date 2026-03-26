import os
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()


@click.group()
@click.version_option(package_name="crabshrimp")
def cli():
    """虾兵蟹将 — Multi-agent runtime with collaborative decision-making and autonomous evolution."""


@cli.command()
@click.option("--task", "-t", required=True, help="Task description for the agent team.")
@click.option(
    "--model", "-m",
    default=lambda: os.getenv("CRABSHRIMP_MODEL", "claude-sonnet-4-6"),
    show_default="CRABSHRIMP_MODEL env or claude-sonnet-4-6",
    help="LLM model identifier (LiteLLM format).",
)
@click.option(
    "--step-limit",
    default=lambda: int(os.getenv("CRABSHRIMP_STEP_LIMIT", "50")),
    show_default="CRABSHRIMP_STEP_LIMIT env or 50",
    type=int,
    help="Maximum number of execution steps.",
)
@click.option(
    "--token-budget",
    default=lambda: int(os.getenv("CRABSHRIMP_TOKEN_BUDGET", "100000")),
    show_default="CRABSHRIMP_TOKEN_BUDGET env or 100000",
    type=int,
    help="Maximum token budget for the task.",
)
@click.option(
    "--trace-dir",
    default=lambda: os.getenv("CRABSHRIMP_TRACE_DIR", "./traces"),
    show_default="CRABSHRIMP_TRACE_DIR env or ./traces",
    help="Directory to save trace JSONL files.",
)
@click.option(
    "--db-path",
    default=lambda: os.getenv("CRABSHRIMP_DB_PATH", "./crabshrimp.db"),
    show_default="CRABSHRIMP_DB_PATH env or ./crabshrimp.db",
    help="SQLite database path for persistent agent profiles and task records.",
)
# ── 机制开关 ──────────────────────────────────────────────────
@click.option(
    "--no-coral-meeting",
    is_flag=True,
    default=False,
    help="Disable Coral-Meeting on critical nodes (single-agent mode).",
)
@click.option(
    "--no-classify",
    is_flag=True,
    default=False,
    help="Skip task classification; treat all tasks as 'general'.",
)
@click.option(
    "--no-trace",
    is_flag=True,
    default=False,
    help="Disable JSONL trace output.",
)
@click.option(
    "--no-resource-guard",
    is_flag=True,
    default=False,
    help="Disable Tidal-Pool step/token limits (run until completion).",
)
# ── 隔离开关 ──────────────────────────────────────────────────
@click.option(
    "--no-context-isolation",
    is_flag=True,
    default=False,
    help="Disable context isolation; all agents see full history (debug mode).",
)
@click.option(
    "--no-workspace-isolation",
    is_flag=True,
    default=False,
    help="Disable workspace isolation; no scoped temp directories.",
)
@click.option(
    "--no-exec-isolation",
    is_flag=True,
    default=False,
    help="Disable execution isolation; use LocalSandbox for all agents.",
)
# ── Human-in-the-Loop ─────────────────────────────────────────
@click.option(
    "--hitl/--no-hitl",
    default=False,
    help="Enable Human-in-the-Loop: pause at key checkpoints for human review.",
)
@click.option(
    "--no-hitl-plan",
    is_flag=True,
    default=False,
    help="Skip plan review checkpoint even when HITL is enabled.",
)
@click.option(
    "--no-hitl-critical",
    is_flag=True,
    default=False,
    help="Skip Coral-Meeting decision review checkpoint even when HITL is enabled.",
)
@click.option(
    "--no-hitl-verify",
    is_flag=True,
    default=False,
    help="Skip Verifier failure checkpoint even when HITL is enabled.",
)
# ── 显示开关 ───────────────────────────────────────────────────
@click.option(
    "--no-display",
    is_flag=True,
    default=False,
    help="Disable Rich live panel; fall back to plain log output.",
)
# ── v0.3 演化开关 ──────────────────────────────────────────────
@click.option(
    "--no-skill-extraction",
    is_flag=True,
    default=False,
    help="Disable post-task Skill extraction from trace (no new skills written to DB).",
)
@click.option(
    "--no-skill-injection",
    is_flag=True,
    default=False,
    help="Disable Skill injection into agent system prompts.",
)
@click.option(
    "--bench-threshold",
    default=lambda: float(os.getenv("CRABSHRIMP_BENCH_THRESHOLD", "0.5")),
    show_default="CRABSHRIMP_BENCH_THRESHOLD env or 0.5",
    type=float,
    help="Coral-Meeting topology threshold: agents with win_rate below this are benched.",
)
def run(task, model, step_limit, token_budget, trace_dir, db_path,
        hitl, no_hitl_plan, no_hitl_critical, no_hitl_verify,
        no_coral_meeting, no_classify, no_trace, no_resource_guard,
        no_context_isolation, no_workspace_isolation, no_exec_isolation,
        no_display, no_skill_extraction, no_skill_injection, bench_threshold):
    """Run a task with the multi-agent team."""
    from crabshrimp.config import CrabShrimpConfig
    from crabshrimp.runtime.runner import TaskRunner

    config = CrabShrimpConfig(
        model=model,
        api_base=os.getenv("CRABSHRIMP_API_BASE") or None,
        step_limit=step_limit,
        token_budget=token_budget,
        db_path=db_path,
        coral_meeting_enabled=not no_coral_meeting,
        classify_enabled=not no_classify,
        trace_enabled=not no_trace,
        resource_guard_enabled=not no_resource_guard,
        context_isolation_enabled=not no_context_isolation,
        workspace_isolation_enabled=not no_workspace_isolation,
        exec_isolation_enabled=not no_exec_isolation,
        skill_extraction_enabled=not no_skill_extraction,
        skill_injection_enabled=not no_skill_injection,
        bench_threshold=bench_threshold,
        hitl_enabled=hitl,
        hitl_on_plan=not no_hitl_plan,
        hitl_on_critical=not no_hitl_critical,
        hitl_on_verify_fail=not no_hitl_verify,
        display_enabled=not no_display,
        trace_dir=trace_dir,
    )

    switches = []
    if not config.coral_meeting_enabled:
        switches.append("[red]coral-meeting=OFF[/red]")
    if not config.classify_enabled:
        switches.append("[yellow]classify=OFF[/yellow]")
    if not config.trace_enabled:
        switches.append("[yellow]trace=OFF[/yellow]")
    if not config.resource_guard_enabled:
        switches.append("[yellow]resource-guard=OFF[/yellow]")
    if not config.context_isolation_enabled:
        switches.append("[yellow]context-isolation=OFF[/yellow]")
    if not config.workspace_isolation_enabled:
        switches.append("[yellow]workspace-isolation=OFF[/yellow]")
    if not config.exec_isolation_enabled:
        switches.append("[yellow]exec-isolation=OFF[/yellow]")
    if not config.skill_extraction_enabled:
        switches.append("[yellow]skill-extraction=OFF[/yellow]")
    if not config.skill_injection_enabled:
        switches.append("[yellow]skill-injection=OFF[/yellow]")
    if config.bench_threshold != 0.5:
        switches.append(f"[cyan]bench-threshold={config.bench_threshold}[/cyan]")
    if config.hitl_enabled:
        switches.append("[bold magenta]HITL=ON[/bold magenta]")
    switch_line = "  Switches: " + " | ".join(switches) if switches else ""

    console.print(
        Panel(
            f"[bold cyan]虾兵蟹将[/bold cyan] v0.3\n"
            f"Model: [green]{model}[/green] | Steps: {step_limit} | Tokens: {token_budget}"
            + (f"\n{switch_line}" if switch_line else ""),
            title="🦐 CrabShrimp",
        )
    )

    runner = TaskRunner(config=config)
    result = runner.run(task)

    console.print("\n[bold green]─── Final Output ───[/bold green]")
    console.print(result.get("final_output", ""))
    trace_info = f"Trace: {result.get('trace_path', 'disabled')} | " if config.trace_enabled else ""
    console.print(f"\n[dim]{trace_info}Steps: {result.get('steps_count')}[/dim]")
