# 虾兵蟹将（CrabShrimp）使用教程

> 本教程基于 v0.4.0，覆盖从安装到高级用法的全流程。

---

## 目录

1. [概念速览](#1-概念速览)
2. [安装与配置](#2-安装与配置)
3. [第一个任务](#3-第一个任务)
4. [理解运行时输出](#4-理解运行时输出)
5. [核心机制详解](#5-核心机制详解)
   - 5.1 Dragon-King 动态编排
   - 5.2 Coral-Meeting 协同决策
   - 5.3 Shell-Molting 演化引擎
   - 5.4 Skill 知识库
   - 5.5 Optimizer Agent
   - 5.6 Human-in-the-Loop
   - 5.7 Tidal-Pool 资源守护
6. [CLI 选项完整参考](#6-cli-选项完整参考)
7. [三种配置方式](#7-三种配置方式)
8. [典型场景示例](#8-典型场景示例)
9. [Python API 嵌入式调用](#9-python-api-嵌入式调用)
10. [查看持久化数据](#10-查看持久化数据)
11. [调试与排查](#11-调试与排查)

---

## 1. 概念速览

CrabShrimp 是一个**多智能体协同 + 自主演化**的 Agent 运行时框架。一句话理解它的设计哲学：

```
高质量协同 → 产生丰富 Trace → 驱动团队演化 → 演化后协同更高效
```

运行一个任务时，内部发生的事情：

```
你的任务描述
    │
    ▼
Dragon-King（编排器）
    ├── 1. 任务分类（code / analysis / reasoning / writing / general）
    ├── 2. 生成执行计划（谁做什么、哪些节点是关键节点）
    └── 3. 按计划执行
            ├── 每步：选最合适的 Agent → act()
            ├── 关键节点：触发 Coral-Meeting（多 Agent 辩论 → 投票 → 共识）
            ├── 资源守护：步数/Token 双限，超限优雅退出
            └── HITL（可选）：人工在关键点介入
    │
    ▼（任务结束后）
Shell-Molting：更新各 Agent 贡献分
Optimizer Agent：分析失败步骤，生成 Prompt 改进建议
Skill Extractor：从成功步骤提炼可复用推理技巧
```

**五种内置角色：**

| 角色 | 职责 | 何时出现 |
|------|------|----------|
| Planner | 分析任务，制定执行计划 | 每个任务开始时 |
| Executor | 执行具体子任务 | 最常见的执行角色 |
| Critic | 审查输出，指出问题与风险 | 常出现在关键节点前后 |
| Verifier | 独立核实结论的正确性 | 高可信度要求的任务 |
| Summarizer | 汇总多步结果为最终输出 | 每个任务结束时 |

---

## 2. 安装与配置

### 2.1 克隆与安装

```bash
git clone https://github.com/Xiaoyu-Tao/CrabShrimp.git
cd CrabShrimp
pip install -e ".[dev]"
```

安装完成后验证：

```bash
crabshrimp --version
crabshrimp --help
```

### 2.2 配置 API Key

复制配置模板：

```bash
cp .env.example .env
```

**直连 Anthropic：**

```ini
CRABSHRIMP_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

**使用 OpenAI 兼容代理（转发 Claude）：**

```ini
CRABSHRIMP_MODEL=openai/claude-sonnet-4-6
OPENAI_API_KEY=sk-xxxxxxxx
CRABSHRIMP_API_BASE=https://your-proxy.com/v1
```

**使用 GPT-4o：**

```ini
CRABSHRIMP_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxxxxxxx
```

**使用本地 Ollama：**

```ini
CRABSHRIMP_MODEL=ollama/llama3
# 无需 API Key，确保 Ollama 在本地运行
```

> CrabShrimp 通过 LiteLLM 统一接入，任何 LiteLLM 支持的模型都可以使用。

---

## 3. 第一个任务

```bash
crabshrimp run --task "解释 Transformer 注意力机制的核心思想，并给出一个直觉性类比"
```

你会看到 Rich 实时面板，显示：
- 当前步骤进度（步数 / 步数上限）
- Token 消耗进度条
- 各 Agent 的实时状态与贡献分
- 活动日志（步骤启动、会议事件、HITL 提示等）

任务结束后，终端输出最终结果，同时在 `./traces/` 目录生成 JSONL Trace 文件，在 `./crabshrimp.db` 存储持久化数据。

---

## 4. 理解运行时输出

### 4.1 Rich 实时面板

```
╭─────────────── 🦐 CrabShrimp ────────────────╮
│ 🔄 解释 Transformer 注意力机制  [analysis]    │
│                                               │
│  Steps    ████████░░░░░░░░░░░░░░      4/50    │
│  Tokens   ███░░░░░░░░░░░░░░░░░░  12,000/100k  │
│                                               │
│  Agent            Role      Status    Score   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  planner-001      planner   ✅ done    1.00   │
│  executor-001     executor  🔄 running 0.95   │
│                                               │
│  Step 1  制定执行计划  → planner               │
│  Step 2  深入分析注意力机制  → executor         │
╰─────────────────── running ───────────────────╯
```

进度条颜色含义：
- 绿色：< 80% 用量，正常
- 黄色：80–100%，接近上限（触发过一次软警告）
- 红色：超出上限，即将触发优雅退出

### 4.2 最终输出

任务完成后打印在 `─── Final Output ───` 分隔线后。

### 4.3 Trace 文件

每次任务生成一个 `traces/task_<id>.jsonl` 文件，每行一步：

```json
{
  "step_id": "a1b2c3d4-...",
  "task_id": "d213388e",
  "agent_id": "executor-001",
  "input": "分析注意力机制",
  "reasoning": "注意力机制的核心是...",
  "output": "Transformer 的注意力...",
  "interactions": [],
  "result": "success",
  "timestamp": "2026-03-27T10:00:00+00:00"
}
```

Coral-Meeting 的共识结果以 `"agent_id": "coral-meeting"` 单独记录一行。

---

## 5. 核心机制详解

### 5.1 Dragon-King 动态编排

Dragon-King 是整个框架的"大脑"。它做三件事：

**① 任务分类**

自动将任务分类为 `code` / `analysis` / `reasoning` / `writing` / `general`，决定后续角色组合和 Skill 的调取策略。

```bash
# 关闭分类（所有任务视为 general，省一次 LLM 调用）
crabshrimp run --task "..." --no-classify
```

**② 执行计划生成**

调用 LLM 生成结构化计划，每个步骤包括：
- 角色分配（哪个角色执行）
- 任务描述
- 是否为关键节点（影响是否触发 Coral-Meeting）

**③ 拓扑筛选**

进入 Coral-Meeting 前，自动过滤历史胜率低于 `bench_threshold` 的 Agent，让高质量 Agent 主导决策。

```bash
# 调低筛选阈值（更宽松，更多 Agent 参与会议）
crabshrimp run --task "..." --bench-threshold 0.3
```

---

### 5.2 Coral-Meeting 协同决策

在执行计划的**关键节点**，多个 Agent 会自动召开会议，通过 6 步流程达成共识：

| 步骤 | 内容 |
|------|------|
| Step 1 | 各 Agent 陈述自己对当前问题的立场 |
| Step 2 | SyncP2P 交叉反思：每个 Agent 向其他 Agent 发送定向批评 |
| Step 2.5 | 各 Agent 读取收到的批评，修订自己的立场 |
| Step 3 | 按贡献分加权投票 |
| Step 4 | 裁决（平票时调用 LLM 仲裁） |
| Step 5 | 共识写入 Trace 和数据库 |

贡献分（`contribution_score`）越高的 Agent，在 Step 3 中的投票权重越大。

```bash
# 关闭 Coral-Meeting（单 Agent 顺序执行，速度更快、成本更低）
crabshrimp run --task "..." --no-coral-meeting
```

> **什么时候关闭？** 简单的事实查询、摘要等低风险任务可以关闭，节省 Token 和时间。需要判断权衡、存在争议的任务建议保持开启。

---

### 5.3 Shell-Molting 演化引擎

每次任务结束后，Shell-Molting 自动分析 Trace 信号，更新 Agent 的贡献分：

| 信号 | 归因 Agent | 分数变化 |
|------|-----------|----------|
| Coral-Meeting 立场被采纳 | 胜出 Agent | **+0.10** |
| Verifier 判定 NOT VERIFIED | 最近的上游非评估 Agent | **−0.15** |
| Critic 判定 REJECTED | 最近的上游非评估 Agent | **−0.10** |
| 任务 stopped_early（资源耗尽） | 全体参与 Agent | **−0.05** |

贡献分的变化会**立即持久化**到 SQLite，影响下次同类任务的投票权重。

---

### 5.4 Skill 知识库

**提取（任务结束后自动发生）：**

从成功步骤的 Trace 中，用 LLM 提炼可复用推理技巧，按 `(role, task_category)` 存入 SQLite 的 `skills` 表。每个槽上限 10 条。

**注入（创建 Agent 时自动发生）：**

创建 Agent 前，从 `skills` 表取出历史最优的 3 条 Skill，追加到 system prompt 末尾：

```
## Learned Skills (apply when relevant)
- When analyzing attention mechanisms, always start with the mathematical formulation...
- For code analysis tasks, structure your response with: context → problem → solution...
```

使用次数越多的 Skill 排名越靠前，形成正向强化。

```bash
# 关闭 Skill 提取（不写入知识库）
crabshrimp run --task "..." --no-skill-extraction

# 关闭 Skill 注入（不使用历史知识）
crabshrimp run --task "..." --no-skill-injection
```

---

### 5.5 Optimizer Agent（v0.4）

Shell-Molting 之后，Optimizer Agent 进一步分析失败原因，为低分角色**生成 system prompt 改进建议**：

**触发条件（任一满足）：**
- 某 Agent 的贡献分 delta < −0.05
- 某步骤的 result == "failure"

**排除条件：**
- Critic / Verifier 不会被优化（它们本就是审查角色，给出负面判断是正常的）

**改进建议的形式：**

```
## Prompt Optimization Note
- When executing code analysis tasks, explicitly state assumptions before proceeding.
  If the input is ambiguous, ask a clarifying question in the reasoning field.
```

此建议下次创建相同角色的 Agent 时，会自动注入其 system prompt，形成**持续改进的自愈循环**。

```bash
# 启用 Optimizer（默认关闭，因为需要额外的 LLM 调用）
crabshrimp run --task "..." --optimize
```

---

### 5.6 Human-in-the-Loop（HITL）

HITL 允许你在三个关键检查点**暂停执行并人工干预**：

**检查点 1：执行计划审核**（计划生成后、执行开始前）

```
[HITL] 📋 执行计划待审核，请确认后再开始
────────────────────────────────────────
  Step 1  [planner]   分析任务结构
  Step 2  [executor]  实现核心逻辑  ★ 关键节点
  Step 3  [verifier]  验证结果正确性
────────────────────────────────────────
  [A] 批准，开始执行
  [X] 终止任务
```

**检查点 2：Coral-Meeting 共识审核**（多 Agent 达成共识后）

```
[HITL] 🪸 Coral-Meeting 共识待审核
议题：实现核心逻辑
────────────────────────────────────────
共识内容：注意力分数应通过 softmax 归一化...
────────────────────────────────────────
  [A] 批准共识，继续执行
  [E] 修改共识内容（输入新内容后按空行确认）
  [X] 终止任务
```

**检查点 3：Verifier 失败介入**（Verifier 判定 NOT VERIFIED 后）

```
[HITL] ⚠️  Verifier 判定失败，等待人工决策
────────────────────────────────────────
验证失败原因：输出中存在数学错误...
────────────────────────────────────────
  [A] 忽略验证失败，继续执行
  [E] 提供修订内容（替换当前步骤输出）
  [X] 终止任务
```

```bash
# 开启 HITL（三个检查点全部激活）
crabshrimp run --task "..." --hitl

# 只在 Verifier 失败时介入
crabshrimp run --task "..." --hitl --no-hitl-plan --no-hitl-critical

# 只在计划阶段审核
crabshrimp run --task "..." --hitl --no-hitl-critical --no-hitl-verify
```

---

### 5.7 Tidal-Pool 资源守护

防止任务失控，硬限制两项资源：

| 限制 | 默认值 | 说明 |
|------|--------|------|
| Step Limit | 50 步 | 防止无限循环 |
| Token Budget | 100,000 | 控制 API 费用 |
| 80% 软警告 | 自动 | 只触发一次，不中断执行 |

**优雅退出机制：** 任一资源耗尽时，不会直接截断。而是触发 Summarizer，对已有结果进行汇总，保证有可用的输出。

```bash
# 自定义资源限制
crabshrimp run --task "..." --step-limit 10 --token-budget 20000

# 完全关闭资源守护（不推荐用于生产）
crabshrimp run --task "..." --no-resource-guard
```

---

## 6. CLI 选项完整参考

```
crabshrimp run --task TEXT [OPTIONS]
```

### 基础选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--task / -t` | 必填 | 任务描述 |
| `--model / -m` | `claude-sonnet-4-6` | LiteLLM 模型标识 |
| `--step-limit` | `50` | 最大执行步数 |
| `--token-budget` | `100000` | Token 预算上限 |
| `--trace-dir` | `./traces` | Trace 文件输出目录 |
| `--db-path` | `./crabshrimp.db` | SQLite 数据库路径 |

### 机制开关

| 选项 | 说明 |
|------|------|
| `--no-coral-meeting` | 关闭多 Agent 协同决策，单 Agent 顺序执行 |
| `--no-classify` | 跳过任务分类，固定为 general |
| `--no-trace` | 不写 JSONL Trace 文件 |
| `--no-resource-guard` | 关闭步数/Token 限制 |
| `--no-skill-extraction` | 不从 Trace 提取 Skill |
| `--no-skill-injection` | 不注入历史 Skill |
| `--bench-threshold FLOAT` | 拓扑筛选阈值（默认 0.5） |
| `--optimize` | 开启 Optimizer Agent（默认关闭） |
| `--no-display` | 关闭 Rich 面板，回退为纯文本日志 |

### 隔离开关

| 选项 | 说明 |
|------|------|
| `--no-context-isolation` | 关闭上下文隔离（调试用） |
| `--no-workspace-isolation` | 关闭工作空间隔离 |
| `--no-exec-isolation` | 关闭执行环境隔离 |

### Human-in-the-Loop

| 选项 | 说明 |
|------|------|
| `--hitl` / `--no-hitl` | 总开关（默认关闭） |
| `--no-hitl-plan` | 跳过计划审核检查点 |
| `--no-hitl-critical` | 跳过 Coral-Meeting 共识检查点 |
| `--no-hitl-verify` | 跳过 Verifier 失败检查点 |

---

## 7. 三种配置方式

配置优先级（高到低）：`CLI flag` > `环境变量` > `.env 文件` > `字段默认值`

### 方式一：CLI flag（一次性生效）

```bash
crabshrimp run --task "..." --no-coral-meeting --step-limit 10
```

### 方式二：环境变量（当次 shell 会话）

```bash
CRABSHRIMP_CORAL_MEETING=false CRABSHRIMP_STEP_LIMIT=10 crabshrimp run --task "..."
```

### 方式三：.env 文件（持久化）

```ini
# .env
CRABSHRIMP_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-xxx

CRABSHRIMP_STEP_LIMIT=20
CRABSHRIMP_TOKEN_BUDGET=50000

CRABSHRIMP_CORAL_MEETING=true
CRABSHRIMP_CLASSIFY=true
CRABSHRIMP_SKILL_EXTRACTION=true
CRABSHRIMP_SKILL_INJECTION=true
CRABSHRIMP_OPTIMIZER=false

CRABSHRIMP_HITL=false
CRABSHRIMP_BENCH_THRESHOLD=0.5

CRABSHRIMP_TRACE_DIR=./traces
CRABSHRIMP_DB_PATH=./crabshrimp.db
```

### 完整环境变量列表

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CRABSHRIMP_MODEL` | `claude-sonnet-4-6` | LiteLLM 模型标识 |
| `CRABSHRIMP_API_BASE` | — | 自定义 API Base |
| `CRABSHRIMP_STEP_LIMIT` | `50` | 最大执行步数 |
| `CRABSHRIMP_TOKEN_BUDGET` | `100000` | Token 预算上限 |
| `CRABSHRIMP_CORAL_MEETING` | `true` | Coral-Meeting 开关 |
| `CRABSHRIMP_CLASSIFY` | `true` | 任务分类开关 |
| `CRABSHRIMP_TRACE` | `true` | Trace 写入开关 |
| `CRABSHRIMP_RESOURCE_GUARD` | `true` | 资源守护开关 |
| `CRABSHRIMP_SKILL_EXTRACTION` | `true` | Skill 提取开关 |
| `CRABSHRIMP_SKILL_INJECTION` | `true` | Skill 注入开关 |
| `CRABSHRIMP_OPTIMIZER` | `false` | Optimizer Agent 开关 |
| `CRABSHRIMP_BENCH_THRESHOLD` | `0.5` | 拓扑筛选阈值 |
| `CRABSHRIMP_HITL` | `false` | HITL 总开关 |
| `CRABSHRIMP_HITL_ON_PLAN` | `true` | 计划检查点 |
| `CRABSHRIMP_HITL_ON_CRITICAL` | `true` | Coral-Meeting 检查点 |
| `CRABSHRIMP_HITL_ON_VERIFY_FAIL` | `true` | Verifier 失败检查点 |
| `CRABSHRIMP_DISPLAY` | `true` | Rich 面板开关 |
| `CRABSHRIMP_TRACE_DIR` | `./traces` | Trace 输出目录 |
| `CRABSHRIMP_DB_PATH` | `./crabshrimp.db` | SQLite 数据库路径 |

---

## 8. 典型场景示例

### 场景 A：快速问答（最轻量配置）

不需要协同决策，只要快速得到答案：

```bash
crabshrimp run \
  --task "Python 中 GIL 的作用是什么？" \
  --no-coral-meeting \
  --no-skill-extraction \
  --no-trace \
  --step-limit 5
```

### 场景 B：代码分析（标准配置）

```bash
crabshrimp run \
  --task "分析以下代码的时间复杂度并给出优化建议：[你的代码]" \
  --step-limit 15 \
  --token-budget 30000
```

### 场景 C：高风险决策（开启 HITL）

对重要结论需要人工把关：

```bash
crabshrimp run \
  --task "为我们的产品设计 A/B 测试方案，评估新推荐算法的效果" \
  --hitl \
  --bench-threshold 0.4
```

### 场景 D：持续学习模式（开启 Optimizer）

多次运行同类任务，让系统自我进化：

```bash
# 第一次运行，建立基线
crabshrimp run --task "写一份技术调研报告：大语言模型的评估方法" --optimize

# 后续运行，系统已注入上次优化的 Prompt 建议 + Skill 知识
crabshrimp run --task "写一份技术调研报告：多模态模型的最新进展" --optimize
```

### 场景 E：批量任务（CI/CD 场景，无人值守）

完全自动化，不需要 Rich 面板，输出到日志：

```bash
crabshrimp run \
  --task "审查 PR #123 的代码质量" \
  --no-display \
  --no-hitl \
  --step-limit 20 \
  --token-budget 50000 \
  2>&1 | tee review_output.txt
```

### 场景 F：调试模式（关闭所有隔离）

开发调试时想看到完整历史：

```bash
crabshrimp run \
  --task "..." \
  --no-context-isolation \
  --no-workspace-isolation \
  --no-exec-isolation \
  --no-display
```

---

## 9. Python API 嵌入式调用

如果你想在自己的 Python 代码中直接使用 CrabShrimp：

```python
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.runtime.runner import TaskRunner

# 最简配置
config = CrabShrimpConfig(
    model="claude-sonnet-4-6",
    step_limit=20,
    token_budget=50000,
)

runner = TaskRunner(config=config)
result = runner.run("分析 Transformer 注意力机制的核心思想")

print(result["final_output"])   # 最终结果
print(result["category"])       # 任务分类（code/analysis/...）
print(result["steps_count"])    # 实际执行步数
print(result["stopped_early"])  # 是否因资源限制提前退出
print(result["evolution_deltas"])  # 各 Agent 贡献分变化
```

**高级配置示例：**

```python
config = CrabShrimpConfig(
    model="openai/claude-sonnet-4-6",
    api_base="https://your-proxy.com/v1",
    step_limit=30,
    token_budget=80000,

    # 机制开关
    coral_meeting_enabled=True,
    classify_enabled=True,
    skill_extraction_enabled=True,
    skill_injection_enabled=True,
    optimizer_enabled=True,

    # 演化参数
    bench_threshold=0.4,

    # HITL（Python API 中通常关闭）
    hitl_enabled=False,

    # 显示（嵌入时通常关闭）
    display_enabled=False,

    # 路径
    trace_dir="./my_traces",
    db_path="./my_project.db",
)
```

**异步调用：**

```python
import asyncio
from crabshrimp.config import CrabShrimpConfig
from crabshrimp.runtime.runner import TaskRunner

async def run_task(task: str):
    config = CrabShrimpConfig(display_enabled=False)
    runner = TaskRunner(config=config)
    # runner.run() 内部会 asyncio.run()，直接调用即可
    return runner.run(task)

result = asyncio.run(run_task("你的任务"))
```

---

## 10. 查看持久化数据

CrabShrimp 在 `./crabshrimp.db` 中维护 6 张表，可以用任何 SQLite 工具查看。

### 用命令行查看

```bash
sqlite3 crabshrimp.db

# 查看各 Agent 的贡献分
sqlite3 crabshrimp.db "SELECT agent_id, role, contribution_score FROM agent_profiles ORDER BY contribution_score DESC;"

# 查看已提取的 Skill（按使用次数排序）
sqlite3 crabshrimp.db "SELECT role, task_category, content, usage_count FROM skills ORDER BY usage_count DESC LIMIT 10;"

# 查看 Coral-Meeting 历史胜者
sqlite3 crabshrimp.db "SELECT winner_agent_id, topic, created_at FROM meeting_outcomes ORDER BY created_at DESC LIMIT 5;"

# 查看任务记录
sqlite3 crabshrimp.db "SELECT task_id, description, category, steps_count, stopped_early FROM task_records ORDER BY created_at DESC LIMIT 5;"

# 查看 Prompt 优化建议
sqlite3 crabshrimp.db "SELECT role, task_category, patch, usage_count FROM prompt_optimizations ORDER BY usage_count DESC;"

# 查看各角色胜率统计
sqlite3 crabshrimp.db "SELECT task_category, role, agent_id, wins, total, ROUND(CAST(wins AS REAL)/total, 2) as win_rate FROM role_weights ORDER BY win_rate DESC;"
```

### 表结构速览

| 表 | 核心字段 | 说明 |
|----|----------|------|
| `agent_profiles` | agent_id, role, system_prompt, contribution_score | Agent 档案与贡献分 |
| `task_records` | task_id, description, category, steps_count | 任务执行摘要 |
| `meeting_outcomes` | task_id, winner_agent_id, topic | 每次 Coral-Meeting 结果 |
| `skills` | role, task_category, content, usage_count | 可复用推理 Skill 知识库 |
| `role_weights` | task_category, role, agent_id, wins, total | Agent 拓扑胜率统计 |
| `prompt_optimizations` | role, task_category, patch, usage_count | Prompt 改进建议 |

### 重置数据库

如果你想重新开始（清空所有学到的 Skill 和历史分数）：

```bash
rm crabshrimp.db
# 下次运行时自动重建
```

---

## 11. 调试与排查

### 查看帮助

```bash
crabshrimp --help
crabshrimp run --help
```

### 关闭 Rich 面板看原始日志

```bash
crabshrimp run --task "..." --no-display
```

原始日志包含每个模块的详细输出（`[DragonKing]`、`[TidalPool]`、`[CoralMeeting]` 等前缀）。

### 常见问题

**Q：任务被截断，显示 "⚠️ Partial"**

资源守护触发了优雅退出。已经有 Summarizer 对已完成部分进行了汇总。
- 增大 `--step-limit` 或 `--token-budget`
- 或用 `--no-resource-guard` 完全关闭（不推荐）

**Q：Coral-Meeting 很慢**

Meeting 需要多个 Agent 各自思考 + 交叉反思，会多消耗 Token。
- 简单任务用 `--no-coral-meeting`
- 或提高 `--bench-threshold` 减少参与 Agent 数量

**Q：API Key 报错 / 模型不可用**

检查 `.env` 文件中的 Key 和模型名是否正确。
用 `--model` 临时切换模型测试：

```bash
crabshrimp run --task "你好" --model gpt-4o --step-limit 3
```

**Q：想看到 Agent 详细的推理过程**

查看 `./traces/task_*.jsonl` 文件，每一行都包含完整的 `reasoning` 字段。

**Q：运行测试**

```bash
pytest tests/ -q        # 全套测试
pytest tests/ -v -k hitl  # 只跑 HITL 相关测试
```

---

## 附录：演化飞轮工作原理

多次运行同类任务后，CrabShrimp 会形成正向飞轮：

```
第 1 次运行
  → Shell-Molting 更新贡献分
  → Skill Extractor 提炼推理技巧 → 存入 skills 表
  → Optimizer Agent 生成 Prompt 改进 → 存入 prompt_optimizations 表

第 2 次运行（同类任务）
  → AgentFactory 注入历史 Skill + Prompt 优化建议
  → Agent 执行质量提升
  → Coral-Meeting 中高分 Agent 的权重更大
  → 更高质量的输出 → 更好的 Trace
  → 更好的 Skill 和优化建议 → ...
```

这就是"虾兵蟹将"名字背后的含义：**个体虽小，集体演化**。

---

*MIT License · [GitHub](https://github.com/Xiaoyu-Tao/CrabShrimp)*
