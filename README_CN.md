# 虾兵蟹将（CrabShrimp）

[English README](README_EN.md)

<p align="center">
  <img src="./logo.jpg" alt="CrabShrimp Logo" width="360"/>
</p>

> *Individual pawns, collective intelligence.*

**v0.3.0** · Python 3.11+ · LiteLLM · MIT License

---

## 简介

虾兵蟹将是一个面向**多智能体协同决策与自主演化**的开源 Agent 运行时框架。

它解决的核心问题是：现有多智能体框架要么只关注"如何让多个 Agent 协同"，要么只研究"如何让 Agent 演化"，从未将两者统一设计。虾兵蟹将的设计哲学是让两者形成正向飞轮：

```
高质量协同 → 产生丰富 Trace → 驱动团队演化 → 演化后的 Agent 协同更高效
```

---

## 核心特性

### Dragon-King 动态决策引擎
- 自动对任务进行分类（code / analysis / reasoning / writing / general）
- LLM 生成结构化执行计划，动态分配 5 种 Agent 角色
- 识别计划中的关键节点，触发 Coral-Meeting 集体审议

### Coral-Meeting 协同决策协议
6 步会议流程，在关键节点驱动多 Agent 达成共识：

| 步骤 | 内容 |
|------|------|
| Step 1 | 各方陈述立场 |
| Step 2 | SyncP2P 交叉反思，向对方发送定向批评 |
| Step 2.5 | 各方读取收到的批评，修订自己的立场 |
| Step 3 | 按贡献分数加权投票 |
| Step 4 | 裁决（平票时调用 LLM 仲裁） |
| Step 5 | 共识写入 Trace |

### Shell-Molting 演化引擎
任务结束后自动分析 Trace 信号，更新 Agent 贡献分：

| 信号 | 归因目标 | 变化 |
|------|----------|------|
| Coral-Meeting 立场被采纳 | 胜出 Agent | +0.10 |
| Verifier 判定 NOT VERIFIED | 最近上游非评估 Agent | −0.15 |
| Critic 判定 REJECTED | 最近上游非评估 Agent | −0.10 |
| 任务 stopped_early | 全体参与 Agent | −0.05 |

贡献分影响 Coral-Meeting 投票权重，高贡献 Agent 的意见更受重视。

### Skill 知识库（v0.3）
- **提取**：从成功步骤的 Trace 中自动提炼可复用推理技巧，按 `(role, task_category)` 存入 SQLite
- **注入**：创建 Agent 时将历史最优 Skill 追加到 System Prompt，注入次数越多的 Skill 排名越高
- 每个 `(role, category)` 槽位上限 10 条，防止过拟合

### 拓扑调整（v0.3）
- 跟踪每个 Agent 在 Coral-Meeting 中的历史胜率（`role_weights` 表）
- `bench_threshold`（默认 0.5）：胜率低于阈值的 Agent 自动退出 Coral-Meeting
- 新 Agent 默认胜率 1.0，给予公平起点

### Human-in-the-Loop（HITL）
在关键检查点暂停执行，等待人工审核。三种操作：**[A] 批准** / **[E] 修改** / **[X] 终止**

| 检查点 | 触发时机 | 支持操作 |
|--------|----------|----------|
| 执行计划审核 | 计划生成后、执行开始前 | A / X |
| Coral-Meeting 共识审核 | 多智能体达成共识后 | A / E / X |
| Verifier 失败介入 | Verifier 判定 NOT VERIFIED 后 | A / E / X |

默认关闭（`--hitl` 启用），不影响无人值守的自动化流程。

### Tidal-Pool 资源守护
- Step Limit 硬限制：防止无限循环
- Token Budget 硬限制：控制 API 开销
- 80% 阈值软警告（仅触发一次）
- 两种耗尽场景均触发 Summarizer 优雅退出，保证有输出

### 5 种预设 Agent 角色

| 角色 | 职责 |
|------|------|
| Planner | 分析任务，制定执行计划 |
| Executor | 具体执行子任务 |
| Critic | 审查输出，发现问题与风险 |
| Verifier | 核实结论的准确性 |
| Summarizer | 汇总多步输出为最终结果 |

---

## 快速开始

### 安装

```bash
git clone <repo-url>
cd crabshrimp
pip install -e ".[dev]"
```

### 配置

复制 `.env.example` 并填入你的 API Key：

```bash
cp .env.example .env
```

最简配置（直连 Anthropic）：

```ini
CRABSHRIMP_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-xxx
```

使用 OpenAI 兼容代理：

```ini
CRABSHRIMP_MODEL=openai/claude-sonnet-4-6
OPENAI_API_KEY=sk-xxx
CRABSHRIMP_API_BASE=https://api.example.com/v1
```

### 运行任务

```bash
crabshrimp run --task "分析 Transformer 注意力机制的核心思想"
```

### 常用 CLI 选项

```bash
# 自定义资源限制
crabshrimp run --task "..." --step-limit 10 --token-budget 50000

# 指定模型
crabshrimp run --task "..." --model gpt-4o

# 关闭 Coral-Meeting（单 Agent 顺序执行，速度更快）
crabshrimp run --task "..." --no-coral-meeting

# 关闭 Skill 提取（不从 Trace 中学习）
crabshrimp run --task "..." --no-skill-extraction

# 关闭 Skill 注入（不使用历史 Skill）
crabshrimp run --task "..." --no-skill-injection

# 调整拓扑筛选阈值（默认 0.5）
crabshrimp run --task "..." --bench-threshold 0.3

# 开启人在回路（在三个关键检查点等待人工确认）
crabshrimp run --task "..." --hitl

# 开启 HITL，但只在 Verifier 失败时介入
crabshrimp run --task "..." --hitl --no-hitl-plan --no-hitl-critical

# 不写 Trace 文件
crabshrimp run --task "..." --no-trace

# 查看所有选项
crabshrimp run --help
```

### 机制开关的三种方式

**CLI flag（临时生效）**

```bash
crabshrimp run --task "..." --no-coral-meeting --no-classify --no-trace
```

**环境变量（当次 shell 会话）**

```bash
CRABSHRIMP_CORAL_MEETING=false CRABSHRIMP_TRACE=false crabshrimp run --task "..."
```

**`.env` 文件（持久化配置）**

```ini
CRABSHRIMP_CORAL_MEETING=false
CRABSHRIMP_SKILL_EXTRACTION=false
CRABSHRIMP_BENCH_THRESHOLD=0.3
CRABSHRIMP_HITL=true
CRABSHRIMP_HITL_ON_PLAN=false
```

---

## 项目结构

```
crabshrimp/
├── config.py                # CrabShrimpConfig：全局配置与机制开关
├── cli/
│   └── commands.py          # Click CLI（--no-* 开关）
├── runtime/
│   └── runner.py            # 任务运行器，组装所有模块
├── dragon_king/             # 动态决策引擎
│   ├── orchestrator.py      # DragonKing：主编排器 + 拓扑调整
│   ├── classifier.py        # 任务分类器
│   └── planner.py           # 执行计划生成器
├── coral_meeting/           # 协同决策协议
│   └── meeting.py           # CoralMeeting：6 步会议（含 SyncP2P + 立场修订）
├── tidal_pool/              # 运行时守护
│   ├── resource_guard.py    # Step & Token 双限
│   ├── shell_molting.py     # 演化引擎：Trace 信号 → 贡献分 + role_weights
│   └── workspace.py         # 工作空间隔离
├── evolution/
│   └── skill_extractor.py   # Skill 提取器（LLM 提炼推理技巧）
├── agents/
│   ├── base.py              # BaseAgent 抽象类
│   ├── factory.py           # AgentFactory（含 Skill 注入）
│   ├── registry.py          # AgentRegistry（SQLite 持久化）
│   └── roles/               # 5 种角色实现
├── communication/
│   ├── blackboard.py        # AsyncBlackboard：共享状态
│   └── p2p.py               # SyncP2P：点对点消息队列
├── db/                      # SQLite 数据层
│   ├── agent_repo.py        # Agent 档案（含 contribution_score）
│   ├── meeting_repo.py      # 会议记录
│   ├── skill_repo.py        # Skill 知识库
│   ├── role_weight_repo.py  # 拓扑胜率统计
│   └── task_repo.py         # 任务摘要
├── llm/
│   ├── base.py              # BaseLLMClient 抽象
│   ├── litellm_client.py    # LiteLLM 实现
│   └── prompts/             # 各角色 System Prompt 模板
├── trace/
│   ├── writer.py            # JSONL 写入
│   └── collector.py         # TraceCollector
└── models/                  # Pydantic 数据模型
    ├── agent_profile.py
    ├── trace.py
    └── message.py
```

---

## SQLite 数据库

运行时自动创建 `crabshrimp.db`，包含 5 张表：

| 表 | 内容 |
|----|------|
| `agent_profiles` | Agent 档案，含 `contribution_score` |
| `task_records` | 任务摘要（分类、步数、trace 路径） |
| `meeting_outcomes` | Coral-Meeting 每次会议的胜出方 |
| `skills` | Skill 知识库，含 `usage_count` 排序 |
| `role_weights` | `(task_category, role, agent_id)` 胜率统计 |

---

## Trace 格式

每次任务执行在 `./traces/` 目录下生成一个 JSONL 文件，每行一个 `TraceStep`：

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

Coral-Meeting 的共识结果以 `agent_id: "coral-meeting"` 单独记录一行。

---

## 支持的 LLM

通过 LiteLLM 统一接口，支持任何兼容模型：

| 场景 | model 写法 |
|------|-----------|
| Anthropic 官方直连 | `claude-sonnet-4-6` |
| OpenAI 兼容代理（转发 Claude） | `openai/claude-sonnet-4-6` |
| OpenAI 官方 | `gpt-4o` |
| 本地 Ollama | `ollama/llama3` |

---

## 完整配置参考

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CRABSHRIMP_MODEL` | `claude-sonnet-4-6` | LiteLLM 模型标识符 |
| `CRABSHRIMP_API_BASE` | — | 自定义 API Base（代理服务） |
| `CRABSHRIMP_STEP_LIMIT` | `50` | 最大执行步数 |
| `CRABSHRIMP_TOKEN_BUDGET` | `100000` | Token 预算上限 |
| `CRABSHRIMP_CORAL_MEETING` | `true` | 关键节点是否召开集体会议 |
| `CRABSHRIMP_CLASSIFY` | `true` | 是否调用 LLM 分类任务 |
| `CRABSHRIMP_TRACE` | `true` | 是否写入 JSONL Trace 文件 |
| `CRABSHRIMP_RESOURCE_GUARD` | `true` | 是否启用资源限制 |
| `CRABSHRIMP_SKILL_EXTRACTION` | `true` | 是否从 Trace 提取 Skill |
| `CRABSHRIMP_SKILL_INJECTION` | `true` | 是否将 Skill 注入 System Prompt |
| `CRABSHRIMP_BENCH_THRESHOLD` | `0.5` | 拓扑筛选胜率阈值 |
| `CRABSHRIMP_HITL` | `false` | 是否启用人在回路（总开关） |
| `CRABSHRIMP_HITL_ON_PLAN` | `true` | 执行计划检查点 |
| `CRABSHRIMP_HITL_ON_CRITICAL` | `true` | Coral-Meeting 共识检查点 |
| `CRABSHRIMP_HITL_ON_VERIFY_FAIL` | `true` | Verifier 失败检查点 |
| `CRABSHRIMP_TRACE_DIR` | `./traces` | Trace 文件输出目录 |
| `CRABSHRIMP_DB_PATH` | `./crabshrimp.db` | SQLite 数据库路径 |

---

## 版本路线图

| 版本 | 状态 | 核心能力 |
|------|------|----------|
| v0.1 | ✅ 已发布 | Dragon-King、Coral-Meeting、ResourceGuard、JSONL Trace |
| v0.2a | ✅ 已发布 | SQLite 数据持久化 |
| v0.2b | ✅ 已发布 | 真实结果信号 + Shell-Molting 演化引擎 |
| v0.3 | ✅ 已发布 | Skill 知识库（提取+注入）+ 拓扑调整 + SyncP2P 接入会议 |
| v0.3（HITL）| ✅ 已发布 | Human-in-the-Loop：三个检查点，支持人工审核、修改、终止 |
| v0.4 | 计划中 | Optimizer Agent（分析 Trace 主动重写低效 Prompt）|
| v0.5 | 计划中 | 沙箱执行环境（Docker / E2B）|

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试（56 个测试用例）
pytest tests/ -q

# 代码风格检查
ruff check crabshrimp/
```

---

## 许可证

MIT License
