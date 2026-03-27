# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CrabShrimp** is a Python multi-agent runtime (v0.4.0, MIT) for collaborative decision-making and autonomous evolution. Its core thesis: *"Individual pawns, collective intelligence."* The system orchestrates 5 agent roles through structured consensus, resource governance, and self-evolving skill memory.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run a task
cp .env.example .env   # configure LLM keys once
crabshrimp run --task "Your task here"

# Test suite (83 tests)
pytest tests/ -q

# Run a single test file or test
pytest tests/test_orchestrator.py -q
pytest tests/ -k "test_name" -q

# Lint
ruff check crabshrimp/
```

## Configuration

All runtime toggles live in `crabshrimp/config.py` as a Pydantic `Settings` object (25+ fields). LLM provider, model, API keys, and feature flags (evolution, optimizer, HITL, coral meeting) are set via `.env` — copy `.env.example` to start.

The `crabshrimp run` CLI (`cli/commands.py`) exposes 20+ options that override config at runtime (e.g., `--model`, `--disable-evolution`, `--hitl`).

## Architecture

### Execution Flow

```
TaskRunner (runtime/runner.py)
  └─ DragonKing.run_task() (dragon_king/orchestrator.py)
       ├─ Classify task (dragon_king/classifier.py)
       ├─ Plan steps (dragon_king/planner.py)
       ├─ [HITL checkpoint] → plan review
       ├─ Execute steps via AgentFactory agents
       │    └─ Detect critical nodes → CoralMeeting (coral_meeting/)
       ├─ Collect TraceSteps (trace/)
       └─ ShellMolting post-task
            ├─ Update contribution scores
            ├─ SkillExtractor (evolution/) → SQLite skills table
            └─ OptimizerAgent (optimizer/) → refine underperforming prompts
```

### 12 Core Components

| Component | Path | Purpose |
|---|---|---|
| Dragon-King | `dragon_king/` | Main orchestrator, task classification, step planning |
| Coral-Meeting | `coral_meeting/` | 6-step weighted-voting consensus protocol |
| Tidal-Pool | `tidal_pool/` | Resource guard (steps/tokens), evolution trigger, HITL, workspace |
| Agents | `agents/` | 5 roles (planner, executor, critic, verifier, summarizer) + factory + registry |
| Evolution | `evolution/` | Distills reusable reasoning from traces into skill memory |
| Optimizer | `optimizer/` | Auto-refines role prompts for underperformers (v0.4) |
| Communication | `communication/` | Blackboard (shared state) + P2P messaging |
| Database | `db/` | SQLite repos: agents, tasks, meetings, skills, role_weights, prompt_optimizations |
| LLM | `llm/` | LiteLLM adapter + per-role system prompts |
| Trace | `trace/` | JSONL trace collection and persistence (`traces/`) |
| Display | `display/` | Rich real-time terminal UI with panels |
| Models | `models/` | Pydantic: `AgentProfile`, `TraceStep`, `Message` |

### Agent Roles

Agents are created by `agents/factory.py` which injects role-specific skills from the DB and optimizer refinements. The 5 roles: **planner**, **executor**, **critic**, **verifier**, **summarizer**. Role win-rates drive topology adaptation (weak performers get benched).

### Database Schema (SQLite)

Six tables managed by `db/` repositories:
- `agent_profiles` — agent state + contribution scores
- `task_records` — task metadata
- `meeting_outcomes` — consensus decisions
- `skills` — extracted reasoning keyed by (role, category)
- `role_weights` — win rates for topology adaptation
- `prompt_optimizations` — v0.4 auto-refinements

## Key Entry Points

- **CLI**: `crabshrimp/cli/commands.py`
- **Orchestrator**: `crabshrimp/dragon_king/orchestrator.py`
- **Component assembly**: `crabshrimp/runtime/runner.py`
- **Agent creation**: `crabshrimp/agents/factory.py`
- **Global config**: `crabshrimp/config.py`
