# CrabShrimp

<p align="center">
  <a href="https://xiaoyu-tao.github.io/CrabShrimp/"><img src="https://img.shields.io/badge/Project-Home-orange.svg" alt="Project Home"></a>
  <a href="https://github.com/Xiaoyu-Tao/CrabShrimp/stargazers"><img src="https://img.shields.io/github/stars/Xiaoyu-Tao/CrabShrimp" alt="GitHub Repo stars"></a>
  <a href="https://github.com/Xiaoyu-Tao/CrabShrimp/network/members"><img src="https://img.shields.io/github/forks/Xiaoyu-Tao/CrabShrimp" alt="GitHub forks"></a>
  <a href="https://xiaoyu-tao.github.io/CrabShrimp/"><img src="https://img.shields.io/badge/docs-latest-blue.svg" alt="Docs"></a>
</p>

<p align="center">
  <a href="./README_CN.md">中文文档</a> · <a href="./TUTORIAL_CN.md">使用教程</a>
</p>

<p align="center">
  <img src="./logo.jpg" alt="CrabShrimp Logo" width="360"/>
</p>

> *Individual pawns, collective intelligence.*

**v0.4.0** · Python 3.11+ · LiteLLM · MIT License

---

## 🗞️ News

- **[2026-03-27]** 🎉 CrabShrimp v0.4.0 is officially released!
- **[2026-03-26]** CrabShrimp v0.3.0 released.

---

## Overview

<p align="center">
  <img src="./pipeline.png" alt="CrabShrimp Architecture" width="860"/>
</p>

CrabShrimp is an open-source multi-agent runtime for **collaborative decision-making and autonomous evolution**.

Its core thesis is simple:

> Most multi-agent frameworks focus on either coordination or evolution, but rarely design both as a single feedback loop.

CrabShrimp treats them as a flywheel:

```text
Better collaboration -> richer traces -> stronger evolution -> better collaboration
```

The current version already includes:

- role-based multi-agent execution
- critical-node deliberation through Coral-Meeting
- resource governance through Tidal-Pool
- SQLite-backed persistence
- post-task evolution signals
- skill extraction and injection
- human-in-the-loop review checkpoints

---

## Core Features

### Dragon-King Dynamic Orchestrator

- Classifies tasks into `code`, `analysis`, `reasoning`, `writing`, or `general`
- Generates a structured execution plan with role assignments
- Detects critical nodes and triggers multi-agent deliberation

### Coral-Meeting Consensus Protocol

CrabShrimp uses a dedicated consensus layer for critical decisions:

| Step | Description |
|------|-------------|
| 1 | Each participant states its position |
| 2 | Participants critique one another through SyncP2P |
| 2.5 | Each participant receives targeted critiques |
| 3 | Weighted voting based on contribution scores |
| 4 | Arbitration if the top candidates tie |
| 5 | Consensus is written to trace and persistence |

### Shell-Molting Evolution Engine

After each task, CrabShrimp analyzes trace signals and updates agent contribution scores:

| Signal | Attribution Target | Delta |
|--------|--------------------|-------|
| Coral-Meeting position adopted | winning agent | +0.10 |
| Verifier returns `NOT VERIFIED` | nearest upstream producer | -0.15 |
| Critic returns `REJECTED` | nearest upstream producer | -0.10 |
| task stopped early | all producing agents | -0.05 |

These contribution scores directly affect future Coral-Meeting voting weights.

### Optimizer Agent (v0.4)

After each task, the Optimizer Agent analyzes trace signals and evolution deltas to identify underperforming roles, then generates targeted system prompt improvements:

- **Trigger**: any agent whose contribution score dropped by more than 0.05, or any step that ended in `failure`
- **Evaluator roles excluded**: Critic and Verifier are never targeted (they are expected to reject)
- **Output**: concise behavioral instruction appended to the role's system prompt on the next run
- **Storage**: `prompt_optimizations` table in SQLite, capped at 5 entries per `(role, task_category)` slot
- **Injection**: at agent creation time, the top optimization note is appended to the system prompt (same mechanism as Skill injection)
- **Enabled with**: `--optimize` flag or `CRABSHRIMP_OPTIMIZER=true` env var (off by default)

### Skill Memory and Injection

- **Extraction**: reusable reasoning skills are distilled from successful trace steps and stored in SQLite
- **Injection**: top historical skills are appended to an agent's system prompt before execution
- Skills are stored per `(role, task_category)` bucket, with a cap to prevent overgrowth

### Topology Adaptation

- Tracks per-agent historical win rates in Coral-Meeting
- Uses `bench_threshold` to temporarily bench weak performers from future deliberation
- New agents default to a fair starting win rate of `1.0`

### Human-in-the-Loop

Optional review checkpoints pause execution for human approval, editing, or termination:

| Checkpoint | Trigger | Supported Actions |
|------------|---------|-------------------|
| Plan review | after planning, before execution | approve / terminate |
| Consensus review | after Coral-Meeting | approve / edit / terminate |
| Verifier failure review | after verification failure | approve / edit / terminate |

HITL is disabled by default and does not interfere with fully autonomous runs.

### Tidal-Pool Resource Governance

- hard step limit
- hard token budget
- 80% early warning threshold
- graceful wrap-up through summarization when limits are hit

### Built-in Roles

| Role | Responsibility |
|------|----------------|
| Planner | analyze the task and prepare execution structure |
| Executor | carry out the actual subtask |
| Critic | identify flaws, risks, and missing pieces |
| Verifier | independently validate correctness |
| Summarizer | synthesize final output |

---

## Quick Start

### Installation

```bash
git clone <repo-url>
cd crabshrimp
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Minimal setup for Anthropic:

```ini
CRABSHRIMP_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-xxx
```

Using an OpenAI-compatible proxy:

```ini
CRABSHRIMP_MODEL=openai/claude-sonnet-4-6
OPENAI_API_KEY=sk-xxx
CRABSHRIMP_API_BASE=https://api.example.com/v1
```

### Run a Task

```bash
crabshrimp run --task "Explain the core idea behind Transformer attention"
```

### Common CLI Examples

```bash
# Custom resource limits
crabshrimp run --task "..." --step-limit 10 --token-budget 50000

# Change model
crabshrimp run --task "..." --model gpt-4o

# Disable Coral-Meeting
crabshrimp run --task "..." --no-coral-meeting

# Disable skill extraction
crabshrimp run --task "..." --no-skill-extraction

# Disable skill injection
crabshrimp run --task "..." --no-skill-injection

# Lower the bench threshold
crabshrimp run --task "..." --bench-threshold 0.3

# Enable human-in-the-loop
crabshrimp run --task "..." --hitl

# Only enable HITL on verifier failure
crabshrimp run --task "..." --hitl --no-hitl-plan --no-hitl-critical

# Disable trace file output
crabshrimp run --task "..." --no-trace
```

### Three Ways to Configure Switches

**1. CLI flags**

```bash
crabshrimp run --task "..." --no-coral-meeting --no-classify --no-trace
```

**2. Environment variables**

```bash
CRABSHRIMP_CORAL_MEETING=false CRABSHRIMP_TRACE=false crabshrimp run --task "..."
```

**3. `.env` file**

```ini
CRABSHRIMP_CORAL_MEETING=false
CRABSHRIMP_SKILL_EXTRACTION=false
CRABSHRIMP_BENCH_THRESHOLD=0.3
CRABSHRIMP_HITL=true
CRABSHRIMP_HITL_ON_PLAN=false
```

---

## Project Structure

```text
crabshrimp/
├── config.py                # global runtime configuration
├── cli/
│   └── commands.py          # Click CLI entrypoints and switches
├── runtime/
│   └── runner.py            # task runner and component assembly
├── dragon_king/
│   ├── orchestrator.py      # main orchestrator and topology logic
│   ├── classifier.py        # task classifier
│   └── planner.py           # execution plan generator
├── coral_meeting/
│   └── meeting.py           # critical-node deliberation protocol
├── tidal_pool/
│   ├── resource_guard.py    # step/token governance
│   ├── shell_molting.py     # post-task evolution engine
│   ├── human_gate.py        # human-in-the-loop checkpoints
│   └── workspace.py         # isolated workspaces
├── evolution/
│   └── skill_extractor.py   # reusable skill extraction
├── agents/
│   ├── base.py              # BaseAgent abstraction
│   ├── factory.py           # agent factory and skill injection
│   ├── registry.py          # role registry and persistence integration
│   └── roles/               # planner / executor / critic / verifier / summarizer
├── communication/
│   ├── blackboard.py        # shared state and topic-based messaging
│   └── p2p.py               # point-to-point message queue
├── db/
│   ├── agent_repo.py
│   ├── connection.py
│   ├── meeting_repo.py
│   ├── role_weight_repo.py
│   ├── skill_repo.py
│   └── task_repo.py
├── llm/
│   ├── base.py              # abstract LLM client
│   ├── litellm_client.py    # LiteLLM adapter
│   └── prompts/             # role system prompts
├── trace/
│   ├── writer.py            # JSONL writer
│   └── collector.py         # in-memory + persistent trace collection
└── models/
    ├── agent_profile.py
    ├── trace.py
    └── message.py
```

---

## SQLite Persistence

At runtime, CrabShrimp creates `crabshrimp.db` and manages at least these tables:

| Table | Purpose |
|-------|---------|
| `agent_profiles` | persistent agent profiles and contribution scores |
| `task_records` | task summary, category, step count, trace path |
| `meeting_outcomes` | Coral-Meeting winners |
| `skills` | extracted skill memory with usage counts |
| `role_weights` | historical win-rate tracking for topology adaptation |

---

## Trace Format

Each task produces a JSONL trace file under `./traces/` unless trace persistence is disabled:

```json
{
  "step_id": "a1b2c3d4-...",
  "task_id": "d213388e",
  "agent_id": "executor-001",
  "input": "Implement the attention mechanism",
  "reasoning": "...",
  "output": "...",
  "interactions": [
    {"agent_id": "critic-001", "reaction": "disagree", "content": "..."}
  ],
  "result": "success",
  "timestamp": "2026-03-26T10:00:00+00:00"
}
```

Coral-Meeting outputs are recorded as dedicated trace steps with `agent_id: "coral-meeting"`.

---

## Supported Models

CrabShrimp uses LiteLLM as a unified adapter, so it can work with any supported backend:

| Scenario | Model String |
|----------|--------------|
| Anthropic direct | `claude-sonnet-4-6` |
| OpenAI-compatible proxy | `openai/claude-sonnet-4-6` |
| OpenAI direct | `gpt-4o` |
| Local Ollama | `ollama/llama3` |

---

## Configuration Reference

| Variable | Default | Meaning |
|----------|---------|---------|
| `CRABSHRIMP_MODEL` | `claude-sonnet-4-6` | LiteLLM model identifier |
| `CRABSHRIMP_API_BASE` | — | custom API base |
| `CRABSHRIMP_STEP_LIMIT` | `50` | max execution steps |
| `CRABSHRIMP_TOKEN_BUDGET` | `100000` | max token budget |
| `CRABSHRIMP_CORAL_MEETING` | `true` | enable critical-node deliberation |
| `CRABSHRIMP_CLASSIFY` | `true` | enable task classification |
| `CRABSHRIMP_TRACE` | `true` | persist JSONL trace files |
| `CRABSHRIMP_RESOURCE_GUARD` | `true` | enforce step/token limits |
| `CRABSHRIMP_CONTEXT_ISOLATION` | `true` | isolate critic/verifier history |
| `CRABSHRIMP_WORKSPACE_ISOLATION` | `true` | allocate scoped workspaces |
| `CRABSHRIMP_EXEC_ISOLATION` | `true` | enable subprocess execution isolation |
| `CRABSHRIMP_SKILL_EXTRACTION` | `true` | extract reusable skills after tasks |
| `CRABSHRIMP_SKILL_INJECTION` | `true` | inject top skills into prompts |
| `CRABSHRIMP_BENCH_THRESHOLD` | `0.5` | meeting topology threshold |
| `CRABSHRIMP_HITL` | `false` | master switch for human-in-the-loop |
| `CRABSHRIMP_HITL_ON_PLAN` | `true` | pause after planning |
| `CRABSHRIMP_HITL_ON_CRITICAL` | `true` | pause after Coral-Meeting |
| `CRABSHRIMP_HITL_ON_VERIFY_FAIL` | `true` | pause on verifier failure |
| `CRABSHRIMP_TRACE_DIR` | `./traces` | trace directory |
| `CRABSHRIMP_DB_PATH` | `./crabshrimp.db` | SQLite database path |

---

## Roadmap

| Version | Status | Highlights |
|---------|--------|------------|
| v0.1 | released | Dragon-King, Coral-Meeting, ResourceGuard, JSONL trace |
| v0.2a | released | SQLite persistence |
| v0.2b | released | Shell-Molting evolution signals |
| v0.3 | released | skill extraction/injection, topology adaptation, SyncP2P in meetings |
| v0.3 HITL | released | human checkpoints for planning, consensus, and verification |
| v0.4 | released | Optimizer Agent: analyzes trace signals and refines role prompts automatically |
| v0.5 | planned | stronger sandbox backends such as Docker / E2B |

---

## Development

```bash
# install dev dependencies
pip install -e ".[dev]"

# run tests
pytest tests/ -q

# lint
ruff check crabshrimp/
```

Current test suite: **70 passing tests**.

---

## License

MIT License
