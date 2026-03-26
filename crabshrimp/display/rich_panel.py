"""Rich live panel for real-time CrabShrimp task visualization."""
from __future__ import annotations

from collections import deque
from typing import Optional

from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class RichDisplay:
    """
    Context-manager that renders a live Rich panel during task execution.

    Usage::

        with RichDisplay(task="...", step_limit=50, token_budget=100_000) as display:
            display.set_category("code")
            display.begin_step(1, "Plan the task", "planner", "planner-001")
            ...
    """

    _STATUS_ICON = {
        "running": "🔄",
        "paused": "⏸ ",
        "done": "✅",
        "partial": "⚠️ ",
        "error": "❌",
    }

    def __init__(
        self,
        task: str,
        step_limit: int,
        token_budget: int,
        enabled: bool = True,
    ) -> None:
        self._task = task
        self._step_limit = step_limit
        self._token_budget = token_budget
        self._enabled = enabled

        self._live: Optional[Live] = None
        self._category = "general"
        self._steps_used = 0
        self._tokens_used = 0
        self._status = "running"

        # agent_id → {role, status, score}
        self._agents: dict[str, dict] = {}
        self._log: deque[str] = deque(maxlen=8)

    # ── Context manager ─────────────────────────────────────────────────────

    def __enter__(self) -> "RichDisplay":
        if self._enabled:
            self._live = Live(
                self._render(),
                refresh_per_second=4,
                transient=False,
            )
            self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)
            self._live = None

    # ── Public update API ────────────────────────────────────────────────────

    def set_category(self, category: str) -> None:
        self._category = category
        self._refresh()

    def begin_step(
        self, step_num: int, description: str, role: str, agent_id: str, score: float = 1.0
    ) -> None:
        self._steps_used = step_num
        prev = self._agents.get(agent_id, {})
        self._agents[agent_id] = {
            "role": role,
            "status": "running",
            "score": prev.get("score", score),
        }
        short = description[:60] + ("…" if len(description) > 60 else "")
        self._log.append(f"[cyan]Step {step_num}[/cyan]  {short}  [dim]→ {role}[/dim]")
        self._refresh()

    def end_step(self, agent_id: str, result: str = "success") -> None:
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = "done" if result == "success" else "error"
        self._refresh()

    def update_tokens(self, tokens_used: int) -> None:
        self._tokens_used = tokens_used
        self._refresh()

    def update_agent_score(self, agent_id: str, score: float) -> None:
        if agent_id in self._agents:
            self._agents[agent_id]["score"] = score
            self._refresh()

    def begin_meeting(self, topic: str, participant_count: int) -> None:
        short = topic[:55] + ("…" if len(topic) > 55 else "")
        self._log.append(
            f"[magenta]🪸 Meeting[/magenta]  {short}  [dim]({participant_count} agents)[/dim]"
        )
        self._refresh()

    def end_meeting(self, consensus_preview: str) -> None:
        short = consensus_preview[:60] + ("…" if len(consensus_preview) > 60 else "")
        self._log.append(f"[magenta]  Consensus[/magenta]  {short}")
        self._refresh()

    def hitl_pause(self, checkpoint: str) -> None:
        """Call before blocking on human input; stops the live display."""
        self._status = "paused"
        self._log.append(f"[yellow]⏸  HITL[/yellow]  {checkpoint}")
        self._refresh()
        if self._live:
            self._live.stop()

    def hitl_resume(self) -> None:
        """Call after human input completes; restarts the live display."""
        self._status = "running"
        if self._live:
            self._live.start()
        self._refresh()

    def log(self, message: str) -> None:
        self._log.append(message)
        self._refresh()

    def complete(self, stopped_early: bool = False) -> None:
        self._status = "partial" if stopped_early else "done"
        if stopped_early:
            self._log.append("[yellow]⚠️  Partial result — resource limit reached[/yellow]")
        else:
            self._log.append("[green]✅  Task complete[/green]")
        self._refresh()

    # ── Rendering ────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._live and self._live.is_started:
            self._live.update(self._render())

    def _make_bar(self, pct: float, width: int = 28) -> Text:
        pct = min(pct, 1.0)
        filled = int(pct * width)
        color = "green" if pct < 0.80 else "yellow" if pct < 1.0 else "red"
        bar = "█" * filled + "░" * (width - filled)
        return Text(bar, style=color)

    def _render(self) -> Panel:
        icon = self._STATUS_ICON.get(self._status, "🔄")

        # ── Header ───────────────────────────────────────────────
        header = Text()
        header.append(f"{icon} ", "")
        header.append(self._task[:80], "bold white")
        header.append(
            f"  [{self._category}]",
            "dim cyan",
        )

        # ── Progress table ────────────────────────────────────────
        prog = Table(box=None, show_header=False, padding=(0, 1))
        prog.add_column(width=7, style="dim")
        prog.add_column(min_width=28)
        prog.add_column(width=18, justify="right", style="dim")

        step_pct = self._steps_used / self._step_limit if self._step_limit else 0
        tok_pct = self._tokens_used / self._token_budget if self._token_budget else 0

        prog.add_row("Steps", self._make_bar(step_pct), f"{self._steps_used}/{self._step_limit}")
        prog.add_row(
            "Tokens",
            self._make_bar(tok_pct),
            f"{self._tokens_used:,}/{self._token_budget:,}",
        )

        # ── Agent table ────────────────────────────────────────────
        agent_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold blue")
        agent_table.add_column("Agent", style="cyan", min_width=16, max_width=22)
        agent_table.add_column("Role", min_width=10, max_width=12)
        agent_table.add_column("Status", min_width=10)
        agent_table.add_column("Score", min_width=6, justify="right")

        _status_icon = {"running": "🔄", "done": "✅", "error": "❌", "idle": "⏳"}
        for agent_id, info in self._agents.items():
            st = info.get("status", "idle")
            score = info.get("score", 1.0)
            score_color = "green" if score >= 1.0 else "yellow" if score >= 0.85 else "red"
            agent_table.add_row(
                agent_id[:22],
                info.get("role", ""),
                f"{_status_icon.get(st, '⏳')} {st}",
                f"[{score_color}]{score:.2f}[/{score_color}]",
            )

        # ── Activity log ───────────────────────────────────────────
        log_text = Text()
        for line in self._log:
            log_text.append_text(Text.from_markup(line))
            log_text.append("\n")

        content = Group(
            header,
            Text(""),
            prog,
            Text(""),
            agent_table if self._agents else Text("[dim]No agents yet[/dim]"),
            Text(""),
            log_text,
        )

        border_color = {
            "running": "blue",
            "paused": "yellow",
            "done": "green",
            "partial": "yellow",
            "error": "red",
        }.get(self._status, "blue")

        return Panel(
            content,
            title="[bold]🦐 CrabShrimp[/bold]",
            subtitle=f"[dim]{self._status}[/dim]",
            border_style=border_color,
        )
